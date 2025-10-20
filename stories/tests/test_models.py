from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from story_requests.models import StoryRequest
from stories.models import Scene, Story


@pytest.mark.django_db
def test_slug_uniqueness(story_request):
    first_story = Story.objects.create(
        request=story_request,
        owner=story_request.user,
        child=story_request.child,
        title="داستان مشترک",
        lang="fa",
        reading_level="k1",
        plan_source=story_request.plan,
    )
    story_request_2 = story_request.__class__.objects.create(
        user=story_request.user,
        child=story_request.child,
        lang="fa",
        reading_level="k1",
        theme="Theme 2",
        plan=StoryRequest.Plan.FREE,
        status=StoryRequest.Status.REVIEW_PENDING,
        queue_priority=StoryRequest.PRIORITY_FREE,
        characters_json=[{"name": "Reza", "role": "hero"}],
    )
    story2 = Story.objects.create(
        request=story_request_2,
        owner=story_request_2.user,
        child=story_request_2.child,
        title="داستان مشترک",
        lang="fa",
        reading_level="k1",
        plan_source=story_request_2.plan,
    )
    assert story2.slug != first_story.slug
    assert story2.slug.endswith("-1")


@pytest.mark.django_db
def test_publish_requires_public_visibility(story):
    story.status = Story.Status.PUBLISHED
    story.visibility = Story.Visibility.PRIVATE
    with pytest.raises(ValidationError):
        story.save()


@pytest.mark.django_db
def test_visibility_public_requires_published(story):
    story.visibility = Story.Visibility.PUBLIC
    with pytest.raises(ValidationError):
        story.save()


@pytest.mark.django_db
def test_scene_page_unique(story):
    with pytest.raises(ValidationError):
        Scene.objects.create(story=story, page_no=1, text="duplicate")


@pytest.mark.django_db
def test_is_published_hidden_flag(story):
    story.status = Story.Status.PUBLISHED
    story.visibility = Story.Visibility.PUBLIC
    story.save()
    assert story.is_published
    story.is_hidden = True
    story.save()
    assert not story.is_published
