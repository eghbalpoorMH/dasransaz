from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from billing.exceptions import (
    AmountMismatch,
    BillingError,
    InsufficientWalletBalance,
    InvalidProvider,
    PaymentAlreadySucceeded,
    PaymentNotAllowed,
    PermissionDeniedBilling,
    ProviderUnavailable,
    RefundNotAllowed,
    StoryRequestNotFound,
)

from .models import IdempotencyKey, Payment, ProviderCoinRate, ProviderTransaction, Refund, Wallet, WalletTransaction
from .providers import get_provider_class


@dataclass
class PaymentAction:
    payment: Payment
    action: dict[str, Any]


@dataclass
class WalletPaymentResult:
    payment: Payment
    wallet_balance: int
    coins_spent: int


def _get_provider(code: str):
    provider_class = get_provider_class(code)
    if not provider_class:
        raise InvalidProvider()
    config = settings.BILLING.get("PROVIDERS", {}).get(code, {})
    return provider_class(config=config)


def _log_event(payment: Payment | None, event: str, payload: dict[str, Any] | None = None) -> None:
    ProviderTransaction.objects.create(
        payment=payment,
        event=event,
        payload_json=payload or {},
    )


def _attach_payment_to_story_request(payment: Payment) -> None:
    from story_requests import services as request_services

    try:
        story_request = request_services.get_request_by_intent(payment.intent_id)
    except ValidationError:  # type: ignore[name-defined]
        return

    if story_request.payment_id != payment.id:
        story_request.payment = payment
        story_request.meta_json = story_request.meta_json or {}
        story_request.meta_json.setdefault("last_payment_id", str(payment.uuid))
        story_request.save(update_fields=["payment", "meta_json", "updated_at"])


@transaction.atomic
def create_payment(
    *,
    intent_id: str,
    user,
    provider: Optional[str],
    amount: int,
    description: str | None,
    idempotency_key: str | None,
    return_url: str,
    callback_url: str,
    metadata: dict[str, Any] | None = None,
) -> PaymentAction:
    provider_code = provider or settings.BILLING.get("DEFAULT_PROVIDER", "iran_gw")
    provider_impl = _get_provider(provider_code)

    if Payment.objects.for_intent(intent_id).successful().exists():
        raise PaymentAlreadySucceeded()

    existing_payment: Payment | None = None
    idempotency = None
    if idempotency_key:
        idempotency = (
            IdempotencyKey.objects.select_for_update()
            .filter(key=idempotency_key, scope=IdempotencyKey.Scope.PAYMENT_CREATE)
            .first()
        )
        if idempotency and idempotency.payment:
            existing_payment = idempotency.payment

    from story_requests import services as request_services
    from story_requests.models import StoryRequest

    try:
        story_request = request_services.get_request_by_intent(intent_id)
    except ValidationError as exc:
        raise StoryRequestNotFound() from exc

    if story_request.user_id != user.id:
        raise PermissionDeniedBilling()

    if story_request.plan != StoryRequest.Plan.PAID:
        raise PaymentNotAllowed("این درخواست نیاز به پرداخت ندارد.")

    if story_request.status not in (
        StoryRequest.Status.PAYMENT_REQUIRED,
        StoryRequest.Status.SUBMITTED,
    ):
        raise PaymentNotAllowed()

    if existing_payment:
        action_payload = existing_payment.meta_json.get("last_action", {"type": "noop"})
        return PaymentAction(payment=existing_payment, action=action_payload)

    expected_amount = (story_request.meta_json or {}).get("expected_amount")
    if expected_amount and int(expected_amount) != amount:
        raise AmountMismatch()

    payment = Payment.objects.create(
        user=user,
        provider=provider_code,
        intent_id=intent_id,
        amount=amount,
        description=description,
        meta_json=metadata or {},
    )

    if idempotency_key:
        IdempotencyKey.objects.update_or_create(
            key=idempotency_key,
            defaults={
                "scope": IdempotencyKey.Scope.PAYMENT_CREATE,
                "payment": payment,
            },
        )

    _attach_payment_to_story_request(payment)

    try:
        action = provider_impl.init_payment(payment, return_url, callback_url)
    except BillingError:
        raise
    except Exception as exc:  # pragma: no cover - provider failure
        _log_event(payment, ProviderTransaction.Event.VERIFY_FAIL, {"error": str(exc)})
        raise ProviderUnavailable() from exc

    payment.meta_json = {**payment.meta_json, "return_url": return_url, "last_action": action}
    if action.get("type") == "redirect":
        payment.status = Payment.Status.PENDING
    payment.save(update_fields=["meta_json", "status", "updated_at"])

    _log_event(payment, ProviderTransaction.Event.INIT, {"action": action})
    if action.get("type") == "redirect":
        _log_event(payment, ProviderTransaction.Event.REDIRECT, {"url": action.get("url")})

    return PaymentAction(payment=payment, action=action)


@transaction.atomic
def apply_success(
    payment: Payment,
    *,
    provider_ref: str,
    raw: dict[str, Any] | None = None,
    note: str = "پرداخت با موفقیت انجام شد.",
) -> Payment:
    payment.status = Payment.Status.SUCCESS
    payment.provider_ref = provider_ref
    payment.error_code = None
    payment.error_message = None
    payment.save(update_fields=["status", "provider_ref", "error_code", "error_message", "updated_at"])

    _log_event(payment, ProviderTransaction.Event.VERIFY_OK, raw or {})

    from story_requests import services as request_services

    request_services.mark_paid(payment.intent_id, payment=payment, note=note)

    wallet_credit = _credit_wallet_from_payment(payment)
    if wallet_credit:
        payment.meta_json = {**(payment.meta_json or {}), "wallet_credit": wallet_credit}
        payment.save(update_fields=["meta_json", "updated_at"])

    return payment


@transaction.atomic
def apply_fail(
    payment: Payment,
    *,
    code: str,
    message: str,
    raw: dict[str, Any] | None = None,
) -> Payment:
    payment.status = Payment.Status.FAILED
    payment.error_code = code
    payment.error_message = message
    payment.save(update_fields=["status", "error_code", "error_message", "updated_at"])
    _log_event(payment, ProviderTransaction.Event.VERIFY_FAIL, raw or {"code": code, "message": message})
    return payment


@transaction.atomic
def mark_consumed(payment: Payment) -> Payment:
    if not payment.consumed_at:
        payment.consumed_at = timezone.now()
        payment.save(update_fields=["consumed_at", "updated_at"])
        _log_event(payment, ProviderTransaction.Event.CONSUMED, {})
    return payment


@transaction.atomic
def refund_full(payment: Payment, *, reason: str = "") -> Refund:
    if payment.is_consumed:
        raise RefundNotAllowed()
    provider_impl = _get_provider(payment.provider)
    refund = Refund.objects.create(payment=payment, amount=payment.amount, reason=reason)
    _log_event(payment, ProviderTransaction.Event.REFUND_REQUESTED, {"mode": "full", "amount": payment.amount})
    response = provider_impl.refund(payment, payment.amount, reason)
    status = response.get("status")
    if status == "succeeded":
        refund.mark_processed(Refund.Status.SUCCEEDED, provider_refund_id=response.get("provider_ref"))
        _log_event(payment, ProviderTransaction.Event.REFUND_SUCCEEDED, response)
    elif status == "failed":
        refund.mark_processed(Refund.Status.FAILED, note=response.get("message", ""))
        _log_event(payment, ProviderTransaction.Event.REFUND_FAILED, response)
    else:
        refund.status = Refund.Status.PROCESSING
        refund.save(update_fields=["status", "updated_at"])
    return refund


@transaction.atomic
def refund_partial(payment: Payment, *, amount: int, reason: str = "") -> Refund:
    if not payment.is_consumed:
        raise RefundNotAllowed()
    if amount <= 0 or amount >= payment.amount:
        raise RefundNotAllowed()
    provider_impl = _get_provider(payment.provider)
    refund = Refund.objects.create(payment=payment, amount=amount, reason=reason)
    _log_event(payment, ProviderTransaction.Event.REFUND_REQUESTED, {"mode": "partial", "amount": amount})
    response = provider_impl.refund(payment, amount, reason)
    status = response.get("status")
    if status == "succeeded":
        refund.mark_processed(Refund.Status.SUCCEEDED, provider_refund_id=response.get("provider_ref"))
        _log_event(payment, ProviderTransaction.Event.REFUND_SUCCEEDED, response)
    elif status == "failed":
        refund.mark_processed(Refund.Status.FAILED, note=response.get("message", ""))
        _log_event(payment, ProviderTransaction.Event.REFUND_FAILED, response)
    else:
        refund.status = Refund.Status.PROCESSING
        refund.save(update_fields=["status", "updated_at"])
    return refund


def get_status(payment: Payment, *, user) -> dict[str, Any]:
    if payment.user_id != user.id:
        raise BillingError("PERMISSION_DENIED", "دسترسی مجاز نیست.")
    return {
        "id": str(payment.uuid),
        "status": payment.status,
        "provider": payment.provider,
        "amount": payment.amount,
        "currency": payment.currency,
        "intent_id": payment.intent_id,
        "provider_ref": payment.provider_ref,
        "error_code": payment.error_code,
        "error_message": payment.error_message,
        "consumed_at": payment.consumed_at,
    }


def get_provider_instance(code: str):
    return _get_provider(code)


def _resolve_coin_rate(payment: Payment) -> ProviderCoinRate | None:
    currency = payment.currency or settings.BILLING.get("CURRENCY", "IRR")
    qs = (
        ProviderCoinRate.objects.active()
        .for_provider(payment.provider, currency)
        .order_by("-base_amount")
    )
    return qs.filter(base_amount__lte=payment.amount).first()


def _credit_wallet_from_payment(payment: Payment) -> dict[str, str | int] | None:
    if payment.wallet_transactions.filter(type=WalletTransaction.Type.DEPOSIT).exists():
        return None

    rate = _resolve_coin_rate(payment)
    if not rate:
        return None

    coins = rate.coins_for_amount(payment.amount)
    if coins <= 0:
        return None

    wallet = (
        Wallet.objects.select_for_update()
        .filter(user=payment.user)
        .first()
    )
    if not wallet:
        wallet = Wallet.objects.create(user=payment.user, balance=0)
    wallet.balance += coins
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        type=WalletTransaction.Type.DEPOSIT,
        coins=coins,
        balance_after=wallet.balance,
        payment=payment,
        description=f"Top-up via {payment.provider}",
    )

    return {
        "coins": coins,
        "rate_id": str(rate.uuid),
        "wallet_id": str(wallet.uuid),
    }


@transaction.atomic
def pay_with_wallet(
    *,
    intent_id: str,
    user,
    note: str = "پرداخت با کیف پول انجام شد.",
    description: str | None = None,
) -> WalletPaymentResult:
    from story_requests import services as request_services
    from story_requests.models import StoryRequest

    if (
        Payment.objects.select_for_update()
        .for_intent(intent_id)
        .successful()
        .exists()
    ):
        raise PaymentAlreadySucceeded()

    try:
        story_request = request_services.get_request_by_intent(intent_id)
    except ValidationError as exc:  # type: ignore[name-defined]
        raise StoryRequestNotFound() from exc

    if story_request.user_id != user.id:
        raise PermissionDeniedBilling()

    story_request = (
        StoryRequest.objects.select_for_update()
        .select_related("product", "payment")
        .get(pk=story_request.pk)
    )

    if story_request.plan != StoryRequest.Plan.PAID:
        raise PaymentNotAllowed("این درخواست نیاز به پرداخت ندارد.")

    if story_request.status not in (
        StoryRequest.Status.PAYMENT_REQUIRED,
        StoryRequest.Status.SUBMITTED,
    ):
        raise PaymentNotAllowed()

    product = story_request.product
    if not product or product.coin_price <= 0:
        raise PaymentNotAllowed("برای این درخواست محصول معتبری تنظیم نشده است.")

    wallet = (
        Wallet.objects.select_for_update()
        .filter(user=user)
        .first()
    )

    if not wallet or wallet.balance < product.coin_price:
        raise InsufficientWalletBalance()

    wallet.balance -= product.coin_price
    wallet.save(update_fields=["balance", "updated_at"])

    payment_description = description or f"Wallet payment for {intent_id}"
    payment = Payment.objects.create(
        user=user,
        provider="wallet",
        intent_id=intent_id,
        amount=0,
        description=payment_description,
        status=Payment.Status.SUCCESS,
        meta_json={
            "wallet_spent": product.coin_price,
            "wallet_balance_after": wallet.balance,
            "note": note,
            "last_action": {"type": "wallet"},
        },
    )

    WalletTransaction.objects.create(
        wallet=wallet,
        type=WalletTransaction.Type.WITHDRAW,
        coins=-product.coin_price,
        balance_after=wallet.balance,
        payment=payment,
        description=f"Story request {intent_id}",
    )

    _attach_payment_to_story_request(payment)
    _log_event(
        payment,
        ProviderTransaction.Event.VERIFY_OK,
        {
            "mode": "wallet",
            "coins_spent": product.coin_price,
            "wallet_balance_after": wallet.balance,
        },
    )

    request_services.mark_paid(intent_id, payment=payment, note=note)

    return WalletPaymentResult(payment=payment, wallet_balance=wallet.balance, coins_spent=product.coin_price)
