from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from uuid import uuid4

from story_requests.models import StoryRequest


API_PREFIX = "/api/v1/requests/"


@pytest.mark.django_db
def test_create_free_request_via_api(user, child):
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        API_PREFIX,
        {
            "child_id": child.pk,
            "lang": "fa",
            "reading_level": StoryRequest.ReadingLevel.K1,
            "theme": "ماجراجویی در حمام ایمن",
            "prompt_note": "قصه مهربان و بامزه باشه",
            "plan": StoryRequest.Plan.FREE,
            "characters": [
                {"name": "علی", "role": "hero", "age": 6, "traits": ["کنجکاو", "مهربان"]}
            ],
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["status"] == StoryRequest.Status.QUEUED_FREE
    assert data["queue_type"] == "FREE"
    assert "id" in data

    story_request = StoryRequest.objects.get(user=user, plan=StoryRequest.Plan.FREE)
    detail = client.get(f"{API_PREFIX}{story_request.uuid}/")
    assert detail.status_code == 200
    assert detail.json()["position"] == 0

    list_response = client.get(f"{API_PREFIX}?mine=1")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == data["id"]


@pytest.mark.django_db
def test_payment_init_flow_via_billing_api(user, monkeypatch):
    client = APIClient()
    client.force_authenticate(user=user)

    create_response = client.post(
        API_PREFIX,
        {
            "lang": "fa",
            "reading_level": StoryRequest.ReadingLevel.K1,
            "theme": "داستان پولی",
            "prompt_note": "",
            "plan": StoryRequest.Plan.PAID,
            "characters": [{"name": "Sara", "role": "hero"}],
        },
        format="json",
    )

    assert create_response.status_code == 201, create_response.content
    story_request = StoryRequest.objects.get(user=user, plan=StoryRequest.Plan.PAID)
    assert story_request.status == StoryRequest.Status.PAYMENT_REQUIRED
    story_request.meta_json = {"expected_amount": 150000}
    story_request.save(update_fields=["meta_json", "updated_at"])

    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "sdk", "payload": {"hint": "testing"}}

        def server_verify(self, payment, **kwargs):
            return {"status": "success", "provider_ref": "TEST", "raw": kwargs}

    monkeypatch.setattr("billing.services._get_provider", lambda code: DummyProvider())

    init_response = client.post(
        "/api/v1/payments/init/",
        {
            "intent_id": story_request.public_id,
            "provider": "bazaar_iap",
            "amount": 150000,
            "description": "Story request",
        },
        format="json",
    )

    assert init_response.status_code == 201, init_response.content
    payment_id = init_response.json()["payment_id"]

    verify_response = client.post(
        "/api/v1/payments/bazaar/verify/",
        {
            "intent_id": story_request.public_id,
            "product_id": "product_1",
            "purchase_token": "token",
            "order_id": "order-1",
        },
        format="json",
    )

    assert verify_response.status_code == 200
    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.QUEUED_PAID

    status_response = client.get(f"/api/v1/payments/{payment_id}/status/")
    assert status_response.status_code == 200


@pytest.mark.django_db
def test_user_cannot_access_foreign_request(user, child):
    client = APIClient()
    client.force_authenticate(user=user)

    client.post(
        API_PREFIX,
        {
            "child_id": child.pk,
            "lang": "fa",
            "reading_level": StoryRequest.ReadingLevel.K1,
            "theme": "داستان شخصی",
            "prompt_note": "",
            "plan": StoryRequest.Plan.FREE,
            "characters": [{"name": "Ali", "role": "hero"}],
        },
        format="json",
    )

    foreign_request = StoryRequest.objects.get(user=user)
    other_user = get_user_model().objects.create_user(
        username="other",
        password="password123",
        email="other@example.com",
        phone_number=f"+98914{uuid4().int % 1_000_000:06d}",
    )

    other_client = APIClient()
    other_client.force_authenticate(user=other_user)
    response = other_client.get(f"{API_PREFIX}{foreign_request.uuid}/")
    assert response.status_code == 404
