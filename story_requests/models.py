from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import BaseModel


class StoryRequest(BaseModel):
    """A request submitted by a user to generate a story for their child."""

    class Plan(models.TextChoices):
        FREE = "free", _("Free")
        PAID = "paid", _("Paid")

    class ReadingLevel(models.TextChoices):
        K1 = "k1", _("Kindergarten 1")
        K2 = "k2", _("Kindergarten 2")
        K3 = "k3", _("Kindergarten 3")
        G1 = "g1", _("Grade 1")
        G2 = "g2", _("Grade 2")

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", _("Submitted")
        PAYMENT_REQUIRED = "PAYMENT_REQUIRED", _("Payment required")
        QUEUED_FREE = "QUEUED_FREE", _("Queued (free)")
        QUEUED_PAID = "QUEUED_PAID", _("Queued (paid)")
        IN_PROGRESS = "IN_PROGRESS", _("In progress")
        REVIEW_PENDING = "REVIEW_PENDING", _("Review pending")
        READY_FOR_USER = "READY_FOR_USER", _("Ready for user")
        CANCELED = "CANCELED", _("Canceled")

    PRIORITY_PAID = 10
    PRIORITY_FREE = 100

    OPEN_STATUSES: Sequence[str] = (
        Status.SUBMITTED,
        Status.PAYMENT_REQUIRED,
        Status.QUEUED_FREE,
        Status.QUEUED_PAID,
        Status.IN_PROGRESS,
        Status.REVIEW_PENDING,
    )

    QUEUED_STATUSES: Sequence[str] = (Status.QUEUED_FREE, Status.QUEUED_PAID)

    LANG_DEFAULT = "fa"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="story_requests",
        on_delete=models.CASCADE,
    )
    child = models.ForeignKey(
        "accounts.Child",
        related_name="story_requests",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    product = models.ForeignKey(
        "stories.StoryProduct",
        related_name="story_requests",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    lang = models.CharField(max_length=5, default=LANG_DEFAULT)
    reading_level = models.CharField(
        max_length=3,
        choices=ReadingLevel.choices,
        default=ReadingLevel.K1,
    )
    theme = models.CharField(max_length=200)
    prompt_note = models.TextField(blank=True)
    characters_json = models.JSONField(default=list)
    plan = models.CharField(max_length=10, choices=Plan.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    queue_priority = models.IntegerField(default=PRIORITY_FREE)
    payment = models.ForeignKey(
        "billing.Payment",
        related_name="story_requests",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    position_hint = models.PositiveIntegerField(default=0)
    meta_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("queue_priority", "created_at")
        indexes = [
            models.Index(fields=("status", "queue_priority", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.user})"

    @property
    def public_id(self) -> str:
        return f"req_{self.uuid.hex[:8]}"

    @property
    def queue_type(self) -> str:
        return "PAID" if self.plan == self.Plan.PAID else "FREE"

    @property
    def is_paid_plan(self) -> bool:
        return self.plan == self.Plan.PAID

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    def clean(self) -> None:
        super().clean()
        self._validate_characters()

    def _validate_characters(self) -> None:
        characters = self.characters_json or []
        if not isinstance(characters, list):
            raise ValidationError({"characters_json": _("Character list is invalid.")})

        for entry in characters:
            if not isinstance(entry, dict):
                raise ValidationError({"characters_json": _("Each character must be a mapping.")})

            required_fields = {"name", "role"}
            missing = required_fields.difference(entry.keys())
            if missing:
                raise ValidationError(
                    {"characters_json": _("Missing fields for character: %(fields)s") % {"fields": ", ".join(sorted(missing))}}
                )
            traits = entry.get("traits", [])
            if traits and not isinstance(traits, list):
                raise ValidationError({"characters_json": _("Traits must be a list.")})
            if traits and any(not isinstance(trait, str) for trait in traits):
                raise ValidationError({"characters_json": _("Traits must be text values.")})


class RequestTransition(BaseModel):
    """Audit log of status transitions for a story request."""

    request = models.ForeignKey(
        StoryRequest,
        related_name="transitions",
        on_delete=models.CASCADE,
    )
    from_status = models.CharField(max_length=20, choices=StoryRequest.Status.choices)
    to_status = models.CharField(max_length=20, choices=StoryRequest.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="story_request_transitions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.request.public_id}: {self.from_status} ➜ {self.to_status}"


@dataclass(frozen=True)
class TransitionRule:
    """Defines a valid state transition."""

    source: str
    destination: str

    @property
    def as_tuple(self) -> tuple[str, str]:
        return self.source, self.destination
