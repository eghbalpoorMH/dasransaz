from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from stories import services
from stories.models import Scene, Story


@pytest.mark.django_db
def test_create_story_from_request_creates_scenes(story_request):
    story = services.create_story_from_request(
        story_request,
        title="قصه تازه",
        scenes_data=[{"page_no": 2, "text": "صفحه دوم"}, {"text": "صفحه سوم"}],
    )
    assert story.owner == story_request.user
    assert story.plan_source == story_request.plan
    assert story.status == Story.Status.READY
    pages = list(story.scenes.order_by("page_no").values_list("page_no", flat=True))
    assert pages == [2, 3]


@pytest.mark.django_db
def test_publish_and_unpublish(story):
    services.publish_story(story)
    story.refresh_from_db()
    assert story.status == Story.Status.PUBLISHED
    assert story.visibility == Story.Visibility.PUBLIC
    services.unpublish_story(story)
    story.refresh_from_db()
    assert story.status == Story.Status.READY
    assert story.visibility == Story.Visibility.PRIVATE


@pytest.mark.django_db
def test_publish_hidden_story_not_allowed(story):
    story.is_hidden = True
    story.save()
    with pytest.raises(ValidationError):
        services.publish_story(story)


@pytest.mark.django_db
def test_upsert_scenes_replaces_set(story):
    scene = story.scenes.first()
    services.upsert_scenes(
        story,
        [
            {"id": scene.id, "page_no": 1, "text": "صفحه یک"},
            {"page_no": 2, "text": "صفحه دو"},
        ],
    )
    story.refresh_from_db()
    texts = list(story.scenes.order_by("page_no").values_list("text", flat=True))
    assert texts == ["صفحه یک", "صفحه دو"]
