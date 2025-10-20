from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from story_requests.models import StoryRequest
from stories.models import Story
from stories import services

API_PREFIX = "/api/v1/stories/"


@pytest.mark.django_db
def test_owner_list_excludes_hidden_and_draft(user, story):
    client = APIClient()
    client.force_authenticate(user=user)

    # add draft and hidden stories
    request_hidden = StoryRequest.objects.create(
        user=user,
        child=story.child,
        lang="fa",
        reading_level="k1",
        theme="Hidden",
        plan=StoryRequest.Plan.FREE,
        status=StoryRequest.Status.REVIEW_PENDING,
        queue_priority=StoryRequest.PRIORITY_FREE,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )
    hidden_story = Story.objects.create(
        request=request_hidden,
        owner=user,
        child=story.child,
        title="Hidden story",
        plan_source="free",
        is_hidden=True,
    )
    request_draft = StoryRequest.objects.create(
        user=user,
        child=story.child,
        lang="fa",
        reading_level="k1",
        theme="Draft",
        plan=StoryRequest.Plan.FREE,
        status=StoryRequest.Status.REVIEW_PENDING,
        queue_priority=StoryRequest.PRIORITY_FREE,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )
    Story.objects.create(
        request=request_draft,
        owner=user,
        child=story.child,
        title="Draft story",
        plan_source="free",
        status=Story.Status.DRAFT,
    )

    response = client.get(f"{API_PREFIX}?mine=1")
    assert response.status_code == 200
    data = response.json()
    items = data["results"] if isinstance(data, dict) else data
    slugs = [item["slug"] for item in items]
    assert hidden_story.slug not in slugs


@pytest.mark.django_db
def test_owner_detail_with_scenes(user, story):
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"{API_PREFIX}{story.id}/?include=scenes")
    assert response.status_code == 200
    data = response.json()
    assert "scenes" in data and len(data["scenes"]) == story.scenes.count()


@pytest.mark.django_db
def test_owner_hidden_story_returns_404(user, story):
    story.is_hidden = True
    story.save()
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"{API_PREFIX}{story.id}/?include=scenes")
    assert response.status_code == 404


@pytest.mark.django_db
def test_publish_unpublish_story(user, story):
    client = APIClient()
    client.force_authenticate(user=user)

    publish_response = client.post(f"{API_PREFIX}{story.id}/publish/")
    assert publish_response.status_code == 200
    story.refresh_from_db()
    assert story.status == Story.Status.PUBLISHED

    unpublish_response = client.post(f"{API_PREFIX}{story.id}/unpublish/")
    assert unpublish_response.status_code == 200
    story.refresh_from_db()
    assert story.status == Story.Status.READY


@pytest.mark.django_db
def test_public_feed_and_detail(story):
    services.publish_story(story)
    story.refresh_from_db()

    client = APIClient()
    list_response = client.get("/api/v1/stories/public/")
    assert list_response.status_code == 200
    assert any(item["slug"] == story.slug for item in list_response.json()["results"])

    detail_response = client.get(f"/api/v1/stories/public/{story.slug}/")
    assert detail_response.status_code == 200
    data = detail_response.json()
    assert "slug" in data
    assert "scenes" not in data


@pytest.mark.django_db
def test_public_detail_include_scenes(story):
    services.publish_story(story)
    client = APIClient()
    response = client.get(f"/api/v1/stories/public/{story.slug}/?include=scenes")
    assert response.status_code == 200
    assert len(response.json()["scenes"]) == story.scenes.count()


@pytest.mark.django_db
def test_from_request_creates_story(staff_user, story_request):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    response = client.post(
        f"/api/v1/stories/from-request/{story_request.pk}/",
        {
            "title": "داستان جدید",
            "scenes": [
                {"page_no": 1, "text": "صفحه اول"},
                {"page_no": 2, "text": "صفحه دوم"},
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "داستان جدید"
    assert len(data["scenes"]) == 2


@pytest.mark.django_db
def test_bulk_scenes_requires_staff(user, story):
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.put(
        f"/api/v1/stories/{story.id}/scenes/",
        {"scenes": [{"id": s.id, "page_no": s.page_no, "text": "update"} for s in story.scenes.all()]},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_bulk_scenes_updates(staff_user, story):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    response = client.put(
        f"/api/v1/stories/{story.id}/scenes/",
        {
            "scenes": [
                {"id": story.scenes.first().id, "page_no": 1, "text": "جدید"},
                {"page_no": 2, "text": "دوم"},
            ]
        },
        format="json",
    )
    assert response.status_code == 200
    story.refresh_from_db()
    assert story.scenes.count() == 2
    assert story.scenes.order_by("page_no").first().text == "جدید"
