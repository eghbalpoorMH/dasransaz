from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import BaseModel


class PaymentQuerySet(models.QuerySet):
    def for_intent(self, intent_id: str) -> "PaymentQuerySet":
        return self.filter(intent_id=intent_id)

    def successful(self) -> "PaymentQuerySet":
        return self.filter(status=Payment.Status.SUCCESS)


class Payment(BaseModel):
    class Status(models.TextChoices):
        INITIATED = "initiated", _("Initiated")
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        CANCELED = "canceled", _("Canceled")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="payments",
        on_delete=models.CASCADE,
    )
    provider = models.CharField(max_length=50)
    intent_id = models.CharField(max_length=64, db_index=True)
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=10, default=settings.BILLING.get("CURRENCY", "IRR"))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    description = models.CharField(max_length=255, blank=True, null=True)
    meta_json = models.JSONField(default=dict, blank=True)
    provider_ref = models.CharField(max_length=128, blank=True, null=True)
    error_code = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    consumed_at = models.DateTimeField(blank=True, null=True)

    objects = PaymentQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("provider", "provider_ref"), name="billing_pay_provider_ref_idx"),
            models.Index(fields=("intent_id",), name="billing_pay_intent_idx"),
            models.Index(fields=("status", "created_at"), name="billing_pay_status_created_ix"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("intent_id",),
                condition=Q(status="success"),
                name="unique_success_payment_per_intent",
            ),
            models.UniqueConstraint(
                fields=("provider", "provider_ref"),
                condition=Q(provider_ref__isnull=False),
                name="unique_provider_ref",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable only
        return f"{self.intent_id} - {self.provider} - {self.status}"

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def mark_consumed(self) -> None:
        if not self.consumed_at:
            self.consumed_at = timezone.now()
            self.save(update_fields=["consumed_at", "updated_at"])


class Refund(BaseModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", _("Requested")
        PROCESSING = "processing", _("Processing")
        SUCCEEDED = "succeeded", _("Succeeded")
        FAILED = "failed", _("Failed")

    payment = models.ForeignKey(Payment, related_name="refunds", on_delete=models.CASCADE)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    reason = models.CharField(max_length=255, blank=True)
    provider_refund_id = models.CharField(max_length=128, blank=True, null=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def mark_processed(self, status: str, *, provider_refund_id: str | None = None, note: str = "") -> None:
        if status not in self.Status.values:
            raise ValidationError("وضعیت بازگشت وجه نامعتبر است.")
        self.status = status
        if provider_refund_id:
            self.provider_refund_id = provider_refund_id
        if note:
            self.note = note
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "provider_refund_id", "note", "processed_at", "updated_at"])


class ProviderTransaction(BaseModel):
    class Event(models.TextChoices):
        INIT = "init", _("Init")
        REDIRECT = "redirect", _("Redirect")
        CALLBACK = "callback", _("Callback")
        VERIFY_OK = "verify_ok", _("Verify success")
        VERIFY_FAIL = "verify_fail", _("Verify failed")
        CONSUMED = "consumed", _("Consumed")
        REFUND_REQUESTED = "refund_requested", _("Refund requested")
        REFUND_SUCCEEDED = "refund_succeeded", _("Refund succeeded")
        REFUND_FAILED = "refund_failed", _("Refund failed")

    payment = models.ForeignKey(
        Payment,
        related_name="transactions",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    event = models.CharField(max_length=32, choices=Event.choices)
    payload_json = models.JSONField(default=dict, blank=True)
    ts = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-ts",)


class IdempotencyKey(BaseModel):
    class Scope(models.TextChoices):
        PAYMENT_CREATE = "payment_create", _("Payment create")
        PAYMENT_VERIFY = "payment_verify", _("Payment verify")
        REFUND = "refund", _("Refund")

    key = models.CharField(max_length=128, unique=True)
    scope = models.CharField(max_length=32, choices=Scope.choices)
    payment = models.ForeignKey(
        Payment,
        related_name="idempotency_keys",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("-created_at",)
