from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.managers import UserManager


class BaseModel(models.Model):
    """Abstract base model that provides UUID identifiers and timestamps."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Run model validation before persisting."""
        self.full_clean()
        super().save(*args, **kwargs)

    # Extension points for subclasses through signals.
    def pre_save(self, **kwargs) -> None:  # noqa: D401 - simple hook
        """Hook executed right before saving the model instance."""

    def post_save(self, created: bool, **kwargs) -> None:  # noqa: D401 - simple hook
        """Hook executed right after saving the model instance."""


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """Custom user model keeping username as the primary identifier."""

    username_validator = UnicodeUsernameValidator()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[username_validator],
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
    )
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = ["email", "phone_number"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.username

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self) -> None:
        super().clean()

        username_value = (self.username or "").strip()
        if username_value:
            self.username = username_value.lower()
        else:
            self.username = ""

        email_value = (self.email or "").strip().lower()
        self.email = email_value or None

        phone_value = (self.phone_number or "").strip()
        if phone_value:
            self.phone_number = User.objects.normalize_phone(phone_value)
        else:
            self.phone_number = None

        if not self.username and self.phone_number:
            self.username = User.objects.generate_username_from_phone(
                self.phone_number,
                exclude_pk=self.pk,
            )

        if not self.username:
            raise ValidationError({"username": _("Username is required.")})


class Child(BaseModel):
    """Represents a child profile owned by a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="children",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=150)
    age_years = models.PositiveSmallIntegerField(blank=True, null=True)
    preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("name",)
        unique_together = ("user", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.user.username})"

    @property
    def age(self) -> int | None:
        return self.age_years


class PhoneVerification(BaseModel):
    """Stores verification codes sent to users."""

    phone_number = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
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


@receiver(pre_save)
def _call_base_model_pre_save(sender, instance, **kwargs):
    if isinstance(instance, BaseModel):
        instance.pre_save(**kwargs)


@receiver(post_save)
def _call_base_model_post_save(sender, instance, created, **kwargs):
    if isinstance(instance, BaseModel):
        instance.post_save(created=created, **kwargs)
