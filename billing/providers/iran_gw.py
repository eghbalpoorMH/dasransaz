from __future__ import annotations

from typing import Any

from django.core.exceptions import ImproperlyConfigured

from .base import BaseProvider

try:  # pragma: no cover - optional dependency
    from azbankgateway import bankfactories, models as bank_models
except ImportError:  # pragma: no cover - optional dependency
    bankfactories = None
    bank_models = None


class IranianGatewayProvider(BaseProvider):
    code = "iran_gw"

    def init_payment(self, payment, return_url: str, callback_url: str) -> dict[str, Any]:
        if bankfactories is None:
            raise ImproperlyConfigured("az-iranian-bank-gateways package is required for iran_gw provider")

        factory = bankfactories.BankFactory()
        if bank_models is None:  # pragma: no cover - safe guard
            raise ImproperlyConfigured("az-iranian-bank-gateways models missing")
        gateway = factory.create(bank_models.BankType.ZARINPAL)
        gateway.set_request_data(amount=payment.amount, mobile_number=payment.user.phone_number)
        gateway.set_client_callback_url(callback_url)
        gateway.set_default_callback_url()
        gateway_record = gateway.bank
        gateway_record.extra_information = {
            "intent_id": payment.intent_id,
            "return_url": return_url,
        }
        gateway_record.save()

        return {
            "type": "redirect",
            "url": gateway.redirect_to_bank(),
        }

    def handle_callback(self, request) -> dict[str, Any]:
        if bankfactories is None:
            raise ImproperlyConfigured("az-iranian-bank-gateways package is required for iran_gw provider")

        factory = bankfactories.BankFactory()
        try:
            gateway = factory.discover(request)
        except Exception as exc:  # pragma: no cover - library-level errors
            raise ImproperlyConfigured("درگاه پرداخت در دسترس نیست.") from exc

        bank_record = gateway.bank
        intent_id = bank_record.extra_information.get("intent_id")
        status = "success" if bank_record.is_success else "failed"
        provider_ref = bank_record.ref_id or bank_record.tracking_code
        raw_payload: dict[str, Any] = {
            "amount": bank_record.amount,
            "card_pan": getattr(bank_record, "card_pan", ""),
            "status": status,
        }
        return {
            "intent_id": intent_id,
            "status": status,
            "provider_ref": provider_ref,
            "raw": raw_payload,
            "error_code": getattr(bank_record, "error_code", None),
            "error_message": getattr(bank_record, "error_message", None),
        }
