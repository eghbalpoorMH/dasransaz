from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from uuid import uuid4

from accounts.models import Child


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
