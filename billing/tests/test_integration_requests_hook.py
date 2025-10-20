from __future__ import annotations

import pytest

from billing import services
from story_requests.models import StoryRequest
from story_requests.services import enqueue_request


@pytest.mark.django_db
def test_apply_success_updates_story_request(monkeypatch, user, child):
    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "sdk", "payload": {}}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Paid",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Ali", "role": "hero"}],
        meta_json={"expected_amount": 180000},
    )
    enqueue_request(story_request, actor=user)

    action = services.create_payment(
        intent_id=story_request.public_id,
        user=user,
        provider="bazaar_iap",
        amount=180000,
        description="Story",
        idempotency_key=None,
        return_url="https://example.com",
        callback_url="https://example.com/callback",
        metadata={},
    )

    payment = action.payment
    services.apply_success(payment, provider_ref="ok", raw={})

    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.QUEUED_PAID
    assert story_request.queue_priority == StoryRequest.PRIORITY_PAID
