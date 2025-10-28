from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from billing import services
from billing.exceptions import InsufficientWalletBalance
from billing.models import Payment, ProviderCoinRate, Wallet, WalletTransaction
from story_requests.models import StoryRequest
from story_requests.services import enqueue_request
from stories.models import StoryProduct


@pytest.mark.django_db
def test_payment_success_credits_wallet(user):
    story_request = StoryRequest.objects.create(
        user=user,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid story",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )
    enqueue_request(story_request, actor=user)
    assert story_request.status == StoryRequest.Status.PAYMENT_REQUIRED

    ProviderCoinRate.objects.create(
        provider="iran_gw",
        currency="IRR",
        base_amount=10000,
        coins=5,
        is_active=True,
    )

    payment = Payment.objects.create(
        user=user,
        provider="iran_gw",
        intent_id=story_request.public_id,
        amount=20000,
        description="Wallet top-up",
    )

    services.apply_success(payment, provider_ref="TEST-REF")

    wallet = user.wallet
    assert wallet.balance == 10

    tx = WalletTransaction.objects.get(payment=payment)
    assert tx.coins == 10
    assert payment.meta_json.get("wallet_credit", {}).get("coins") == 10


@pytest.mark.django_db
def test_wallet_payment_consumes_balance(user):
    product = StoryProduct.objects.create(
        title="Gold Pack",
        coin_price=12,
        bazaar_sku="wallet_pack",
    )
    story_request = StoryRequest.objects.create(
        user=user,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Wallet story",
        plan=StoryRequest.Plan.PAID,
        product=product,
        characters_json=[{"name": "Sara", "role": "hero"}],
    )
    enqueue_request(story_request, actor=user)

    wallet = Wallet.objects.create(user=user, balance=20)

    result = services.pay_with_wallet(intent_id=story_request.public_id, user=user)

    story_request.refresh_from_db()
    wallet.refresh_from_db()

    assert story_request.status == StoryRequest.Status.QUEUED_PAID
    assert story_request.queue_priority == StoryRequest.PRIORITY_PAID
    assert result.payment.provider == "wallet"
    assert wallet.balance == 8
    assert result.wallet_balance == 8
    assert result.coins_spent == 12

    tx = WalletTransaction.objects.get(payment=result.payment)
    assert tx.type == WalletTransaction.Type.WITHDRAW
    assert tx.coins == -12
    assert tx.balance_after == 8


@pytest.mark.django_db
def test_wallet_payment_requires_sufficient_balance(user):
    product = StoryProduct.objects.create(
        title="Silver Pack",
        coin_price=30,
        bazaar_sku="wallet_pack_low",
    )
    story_request = StoryRequest.objects.create(
        user=user,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Wallet insufficient",
        plan=StoryRequest.Plan.PAID,
        product=product,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )
    enqueue_request(story_request, actor=user)

    wallet = Wallet.objects.create(user=user, balance=10)

    with pytest.raises(InsufficientWalletBalance):
        services.pay_with_wallet(intent_id=story_request.public_id, user=user)

    wallet.refresh_from_db()
    assert wallet.balance == 10
    assert story_request.status == StoryRequest.Status.PAYMENT_REQUIRED
    assert not WalletTransaction.objects.filter(wallet=wallet).exists()


@pytest.mark.django_db
def test_wallet_info_api(user):
    client = APIClient()
    client.force_authenticate(user=user)

    Wallet.objects.create(user=user, balance=18)

    response = client.get("/api/v1/payments/wallet/")
    assert response.status_code == 200
    assert response.json()["balance"] == 18


@pytest.mark.django_db
def test_wallet_payment_api(user):
    client = APIClient()
    client.force_authenticate(user=user)

    product = StoryProduct.objects.create(
        title="Bronze Pack",
        coin_price=6,
        bazaar_sku="wallet_pack_api",
    )
    story_request = StoryRequest.objects.create(
        user=user,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="API wallet story",
        plan=StoryRequest.Plan.PAID,
        product=product,
        characters_json=[{"name": "Nima", "role": "hero"}],
    )
    enqueue_request(story_request, actor=user)
    Wallet.objects.create(user=user, balance=10)

    response = client.post(
        "/api/v1/payments/wallet/pay/",
        {"intent_id": story_request.public_id},
        format="json",
    )

    assert response.status_code == 200, response.content
    data = response.json()
    assert data["wallet_balance"] == 4
    assert data["coins_spent"] == 6

    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.QUEUED_PAID
