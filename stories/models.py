from __future__ import annotations

from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from slugify import slugify

from accounts.models import BaseModel


class Story(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        READY = "READY", "Ready"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    request = models.OneToOneField(
        "requests.StoryRequest",
        on_delete=models.CASCADE,
        related_name="story",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="stories",
        on_delete=models.CASCADE,
    )
    child = models.ForeignKey(
        "accounts.Child",
        related_name="stories",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    title = models.CharField(max_length=180)
    lang = models.CharField(max_length=5, default="fa")
    reading_level = models.CharField(max_length=20, default="k1")

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.READY,
    )
    visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )

    is_hidden = models.BooleanField(default=False)
    hidden_reason = models.TextField(blank=True, null=True)

    plan_source = models.CharField(max_length=8, default="free")
    cover_url = models.URLField(blank=True, null=True)
    cover_meta = models.JSONField(default=dict, blank=True)

    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(blank=True, null=True)

    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "visibility", "is_hidden", "lang"], name="story_status_visibility_idx"),
            models.Index(fields=["owner", "status"], name="story_owner_status_idx"),
            models.Index(fields=["slug"], name="story_slug_idx"),
        ]
        ordering = ("-published_at", "-created_at")

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"{self.title} ({self.status})"

    def clean(self) -> None:
        super().clean()

        if self.status == self.Status.PUBLISHED and self.visibility != self.Visibility.PUBLIC:
            raise ValidationError({"visibility": "داستان‌های منتشرشده باید عمومی باشند."})

        if self.visibility == self.Visibility.PUBLIC and self.status != self.Status.PUBLISHED:
            raise ValidationError({"visibility": "داستان عمومی باید در وضعیت انتشار باشد."})

        if self.plan_source not in {"free", "paid"}:
            raise ValidationError({"plan_source": "پلن نامعتبر است."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug(self.title)
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_unique_slug(title: str) -> str:
        base_slug = slugify(title)[:200] or "story"
        slug = base_slug
        suffix = 1
        while Story.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug

    @property
    def scenes_count(self) -> int:
        return self.scenes.count()

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED and not self.is_hidden


class Scene(BaseModel):
    story = models.ForeignKey(Story, related_name="scenes", on_delete=models.CASCADE)
    page_no = models.PositiveIntegerField()
    text = models.TextField()
    image_url = models.URLField(blank=True, null=True)
    voice_url = models.URLField(blank=True, null=True)
    timings_json = models.JSONField(default=dict, blank=True)
    annotations_json = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("story", "page_no")
        ordering = ("page_no",)

    def clean(self) -> None:
        super().clean()
        if self.page_no == 0:
            raise ValidationError({"page_no": "شماره صفحه باید از ۱ شروع شود."})

    def __str__(self) -> str:  # pragma: no cover
        return f"Scene {self.page_no} of {self.story_id}"
