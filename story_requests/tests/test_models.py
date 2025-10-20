from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from billing import services as billing_services
from story_requests.models import StoryRequest
from story_requests.services import (
    calc_position,
    enqueue_request,
    transition,
)


@pytest.mark.django_db
def test_enqueue_free_request_transitions(user, child):
    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Dream adventure",
        plan=StoryRequest.Plan.FREE,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )

    enqueue_request(story_request, actor=user)
    story_request.refresh_from_db()

    assert story_request.status == StoryRequest.Status.QUEUED_FREE
    assert story_request.queue_priority == StoryRequest.PRIORITY_FREE
    assert story_request.transitions.count() == 1


@pytest.mark.django_db
def test_payment_flow_moves_request_into_paid_queue(user, child, monkeypatch):
    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K2,
        theme="Space explorers",
        plan=StoryRequest.Plan.PAID,
        characters_json=[{"name": "Sara", "role": "hero"}],
    )

    enqueue_request(story_request, actor=user)
    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.PAYMENT_REQUIRED

    class DummyProvider:
        def init_payment(self, payment, return_url: str, callback_url: str):
            return {"type": "sdk", "payload": {"hint": "testing"}}

        def handle_callback(self, request):
            return {}

    monkeypatch.setattr(billing_services, "_get_provider", lambda code: DummyProvider())

    action = billing_services.create_payment(
        intent_id=story_request.public_id,
        user=user,
        provider="bazaar_iap",
        amount=150000,
        description="Test",
        idempotency_key=None,
        return_url="https://example.com/return",
        callback_url="https://example.com/callback",
        metadata={},
    )

    payment = action.payment
    billing_services.apply_success(payment, provider_ref="TEST", raw={})
    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.QUEUED_PAID
    assert story_request.queue_priority == StoryRequest.PRIORITY_PAID


@pytest.mark.django_db
def test_calc_position_orders_by_created_at(user, child):
    requests = []
    for idx in range(3):
        req = StoryRequest.objects.create(
            user=user,
            child=child,
            lang="fa",
            reading_level=StoryRequest.ReadingLevel.K1,
            theme=f"Theme {idx}",
            plan=StoryRequest.Plan.FREE,
            characters_json=[{"name": "Ali", "role": "hero"}],
        )
        enqueue_request(req, actor=user)
        requests.append(req)

    # Re-fetch in order of creation to avoid stale cached created_at
    ordered = StoryRequest.objects.order_by("created_at")
    assert calc_position(ordered[0]) == 0
    assert calc_position(ordered[1]) == 1
    assert calc_position(ordered[2]) == 2


@pytest.mark.django_db
def test_transition_invalid_path_raises(user, child):
    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Ocean",
        plan=StoryRequest.Plan.FREE,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )

    enqueue_request(story_request, actor=user)
    with pytest.raises(ValidationError):
        transition(story_request, StoryRequest.Status.READY_FOR_USER)
