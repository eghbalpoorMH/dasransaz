from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from billing import services
from billing.models import Payment
from story_requests.models import StoryRequest
from stories.models import StoryProduct
from story_requests.services import enqueue_request


@pytest.mark.django_db
def test_bazaar_verify_success(monkeypatch, user, child):
    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "sdk", "payload": {}}

        def server_verify(self, payment, **kwargs):
            return {"status": "success", "provider_ref": "order-1", "raw": kwargs}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    product = StoryProduct.objects.create(
        title="Premium Coins",
        coin_price=140000,
        bazaar_sku="product-1",
    )

    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        product=product,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 140000},
    )
    enqueue_request(story_request, actor=user)

    client = APIClient()
    client.force_authenticate(user=user)
    client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": story_request.public_id,
            "amount": 140000,
            "provider": "bazaar_iap",
            "description": "Story",
        },
        format="json",
    )

    response = client.post(
        "/api/v1/payments/bazaar/verify/",
        {
            "intent_id": story_request.public_id,
            "product_id": "product-1",
            "purchase_token": "token",
        },
        format="json",
    )

    assert response.status_code == 200
    payment = Payment.objects.get(intent_id=story_request.public_id)
    assert payment.status == Payment.Status.SUCCESS


@pytest.mark.django_db
def test_bazaar_verify_failure(monkeypatch, user, child):
    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "sdk", "payload": {}}

        def server_verify(self, payment, **kwargs):
            return {"status": "failed", "error_code": "INVALID", "raw": kwargs}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    product = StoryProduct.objects.create(
        title="Premium Coins",
        coin_price=140000,
        bazaar_sku="product-1",
    )

    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        product=product,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 140000},
    )
    enqueue_request(story_request, actor=user)

    client = APIClient()
    client.force_authenticate(user=user)
    client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": story_request.public_id,
            "amount": 140000,
            "provider": "bazaar_iap",
            "description": "Story",
        },
        format="json",
    )

    response = client.post(
        "/api/v1/payments/bazaar/verify/",
        {
            "intent_id": story_request.public_id,
            "product_id": "product-1",
            "purchase_token": "token",
        },
        format="json",
    )

    assert response.status_code == 200
    payment = Payment.objects.get(intent_id=story_request.public_id)
    assert payment.status == Payment.Status.FAILED
