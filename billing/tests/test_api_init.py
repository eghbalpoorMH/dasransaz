from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from billing import services
from billing.models import Payment
from story_requests.models import StoryRequest
from story_requests.services import enqueue_request


@pytest.mark.django_db
def test_payment_init_redirect(monkeypatch, user, child):
    request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 200000},
    )
    enqueue_request(request, actor=user)

    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "redirect", "url": "https://bank.example/pay"}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": request.public_id,
            "amount": 200000,
            "provider": "iran_gw",
            "description": "Story",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["action"]["type"] == "redirect"
    payment = Payment.objects.get(uuid=data["payment_id"])
    assert payment.status == Payment.Status.PENDING
    assert payment.provider == "iran_gw"


@pytest.mark.django_db
def test_payment_init_idempotency(monkeypatch, user, child):
    request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 100000},
    )
    enqueue_request(request, actor=user)

    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "sdk", "payload": {}}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    client = APIClient()
    client.force_authenticate(user=user)

    headers = {"HTTP_IDEMPOTENCY_KEY": "idem-1"}
    first = client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": request.public_id,
            "amount": 100000,
            "provider": "bazaar_iap",
            "description": "Story",
        },
        format="json",
        **headers,
    )
    assert first.status_code == 201, first.content

    second = client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": request.public_id,
            "amount": 100000,
            "provider": "bazaar_iap",
            "description": "Story",
        },
        format="json",
        **headers,
    )
    assert second.status_code == 201
    assert first.json()["payment_id"] == second.json()["payment_id"]
