from __future__ import annotations

from types import SimpleNamespace

import pytest

from story_requests.models import StoryRequest
from story_requests.serializers import StoryRequestCreateSerializer
from story_requests.services import enqueue_request


def _build_payload(plan: str = StoryRequest.Plan.FREE) -> dict[str, object]:
    return {
        "lang": "fa",
        "reading_level": StoryRequest.ReadingLevel.K1,
        "theme": "Test theme",
        "prompt_note": "",
        "plan": plan,
        "characters": [{"name": "Ali", "role": "hero"}],
    }


@pytest.mark.django_db
def test_create_serializer_respects_open_request_limit(user):
    for idx in range(2):
        req = StoryRequest.objects.create(
            user=user,
            lang="fa",
            reading_level=StoryRequest.ReadingLevel.K1,
            theme=f"Theme {idx}",
            plan=StoryRequest.Plan.FREE,
            characters_json=[{"name": "Ali", "role": "hero"}],
        )
        enqueue_request(req, actor=user)

    serializer = StoryRequestCreateSerializer(
        data=_build_payload(),
        context={"request": SimpleNamespace(user=user)},
    )

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


@pytest.mark.django_db
def test_create_serializer_allows_paid_request(user):
    serializer = StoryRequestCreateSerializer(
        data=_build_payload(plan=StoryRequest.Plan.PAID),
        context={"request": SimpleNamespace(user=user)},
    )

    assert serializer.is_valid(), serializer.errors
    story_request = serializer.save()
    assert story_request.status == StoryRequest.Status.PAYMENT_REQUIRED

