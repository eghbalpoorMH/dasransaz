from __future__ import annotations

from uuid import uuid4

import pytest

from accounts.models import Child
from story_requests.models import StoryRequest
from stories.models import Story
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    User = get_user_model()
    suffix = f"{uuid4().int % 1_000_000:06d}"
    return User.objects.create_user(
        username=f"parent_{uuid4().hex[:6]}",
        password="password123",
        email="parent@example.com",
        phone_number=f"+98912{suffix}",
    )


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    suffix = f"{uuid4().int % 1_000_000:06d}"
    return User.objects.create_superuser(
        username=f"admin_{uuid4().hex[:6]}",
        password="password123",
        email="admin@example.com",
        phone_number=f"+98913{suffix}",
    )


@pytest.fixture
def child(user):
    return Child.objects.create(user=user, name="Ali", age_years=7)


@pytest.fixture
def story_request(user, child):
    return StoryRequest.objects.create(
        user=user,
        child=child,
        lang="fa",
        reading_level="k1",
        theme="Test theme",
        plan=StoryRequest.Plan.FREE,
        status=StoryRequest.Status.REVIEW_PENDING,
        queue_priority=StoryRequest.PRIORITY_FREE,
        characters_json=[{"name": "Ali", "role": "hero"}],
    )


@pytest.fixture
def story(story_request):
    story = Story.objects.create(
        request=story_request,
        owner=story_request.user,
        child=story_request.child,
        title="قصه تستی",
        lang=story_request.lang,
        reading_level=story_request.reading_level,
        plan_source=story_request.plan,
    )
    story.scenes.create(page_no=1, text="Once upon a time")
    return story
