from __future__ import annotations

from datetime import timedelta
import uuid

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from accounts.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model that authenticates via phone number."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.phone_number

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class PhoneVerification(models.Model):
    """Stores verification codes sent to users."""

    phone_number = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["phone_number", "is_used"]),
        ]
        ordering = ["-created_at"]

    def mark_used(self) -> None:
        self.is_used = True
        self.save(update_fields=["is_used"])

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @classmethod
    def create_code(cls, phone_number: str, code: str) -> "PhoneVerification":
        expiry = timezone.now() + timedelta(minutes=settings.AUTH_VERIFICATION_CODE_EXPIRY_MINUTES)
        return cls.objects.create(
            phone_number=phone_number,
            code_hash=make_password(code),
            expires_at=expiry,
        )

    def verify(self, code: str) -> bool:
        if self.is_used or self.is_expired:
            return False
        return check_password(code, self.code_hash)
