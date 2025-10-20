from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from stories.models import Story


@pytest.mark.django_db
def test_admin_publish_and_hide_actions(staff_user, story):
    client = Client()
    client.force_login(staff_user)

    changelist_url = reverse("admin:stories_story_changelist")

    response = client.post(
        changelist_url,
        {"action": "action_publish", "_selected_action": [story.pk]},
        follow=True,
    )
    assert response.status_code == 200
    story.refresh_from_db()
    assert story.status == Story.Status.PUBLISHED

    response = client.post(
        changelist_url,
        {"action": "action_hide", "_selected_action": [story.pk]},
        follow=True,
    )
    assert response.status_code == 200
    story.refresh_from_db()
    assert story.is_hidden

    response = client.post(
        changelist_url,
        {"action": "action_unhide", "_selected_action": [story.pk]},
        follow=True,
    )
    assert response.status_code == 200
    story.refresh_from_db()
    assert not story.is_hidden

    response = client.post(
        changelist_url,
        {"action": "action_unpublish", "_selected_action": [story.pk]},
        follow=True,
    )
    assert response.status_code == 200
    story.refresh_from_db()
    assert story.status == Story.Status.READY
