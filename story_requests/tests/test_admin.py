from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from story_requests.models import StoryRequest
from story_requests.services import enqueue_request


@pytest.mark.django_db
def test_admin_actions_drive_transitions(staff_user, user, child):
    story_request = StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level=StoryRequest.ReadingLevel.K1,
        theme="Admin flow",
        plan=StoryRequest.Plan.FREE,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )
    enqueue_request(story_request, actor=user)

    client = Client()
    client.force_login(staff_user)
    changelist_url = reverse("admin:requests_storyrequest_changelist")

    response = client.post(
        changelist_url,
        {
            "action": "move_to_in_progress",
            "_selected_action": [str(story_request.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200
    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.IN_PROGRESS

    response = client.post(
        changelist_url,
        {
            "action": "cancel_with_reason",
            "cancellation_reason": "عدم نیاز کاربر",
            "_selected_action": [str(story_request.pk)],
        },
        follow=True,
    )
    assert response.status_code == 200
    story_request.refresh_from_db()
    assert story_request.status == StoryRequest.Status.CANCELED

