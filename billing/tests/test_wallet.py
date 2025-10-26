from __future__ import annotations

import pytest

from billing import services
from billing.models import Payment, ProviderCoinRate, WalletTransaction
from story_requests.models import StoryRequest
from story_requests.services import enqueue_request


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
