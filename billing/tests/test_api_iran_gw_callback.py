from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from billing import services
from billing.models import Payment
from story_requests.models import StoryRequest
from story_requests.services import enqueue_request


@pytest.mark.django_db
def test_iran_gateway_callback_success(monkeypatch, user, child):
    context: dict[str, str] = {}

    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            context["intent"] = payment.intent_id
            return {"type": "redirect", "url": "https://bank.example/pay"}

        def handle_callback(self, request):
            return {
                "intent_id": context["intent"],
                "status": "success",
                "provider_ref": "ref-123",
                "raw": {},
            }

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 120000},
    )
    enqueue_request(story_request, actor=user)

    client = APIClient()
    client.force_authenticate(user=user)
    client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": story_request.public_id,
            "amount": 120000,
            "provider": "iran_gw",
            "description": "Story",
        },
        format="json",
    )

    payment = Payment.objects.get(intent_id=story_request.public_id)
    callback_client = APIClient()
    response = callback_client.post("/api/v1/payments/iran-gw/callback/", {})
    assert response.status_code in (200, 302)
    payment.refresh_from_db()
    story_request.refresh_from_db()
    assert payment.status == Payment.Status.SUCCESS
    assert story_request.status == StoryRequest.Status.QUEUED_PAID


@pytest.mark.django_db
def test_iran_gateway_callback_failure(monkeypatch, user, child):
    context: dict[str, str] = {}

    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            context["intent"] = payment.intent_id
            return {"type": "redirect", "url": "https://bank.example/pay"}

        def handle_callback(self, request):
            return {
                "intent_id": context["intent"],
                "status": "failed",
                "provider_ref": "ref-123",
                "raw": {},
                "error_code": "-1",
                "error_message": "fail",
            }

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 120000},
    )
    enqueue_request(story_request, actor=user)

    client = APIClient()
    client.force_authenticate(user=user)
    client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": story_request.public_id,
            "amount": 120000,
            "provider": "iran_gw",
            "description": "Story",
        },
        format="json",
    )

    payment = Payment.objects.get(intent_id=story_request.public_id)
    callback_client = APIClient()
    response = callback_client.post("/api/v1/payments/iran-gw/callback/", {})
    assert response.status_code in (200, 302)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.FAILED
