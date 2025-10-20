from __future__ import annotations

from django.contrib import admin, messages

from billing import services

from .models import IdempotencyKey, Payment, ProviderTransaction, Refund


class ProviderTransactionInline(admin.TabularInline):
    model = ProviderTransaction
    extra = 0
    can_delete = False
    readonly_fields = ("event", "payload_json", "ts")
    ordering = ("-ts",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "user",
        "provider",
        "intent_id",
        "amount",
        "status",
        "consumed_at",
        "created_at",
    )
    list_filter = ("provider", "status", "created_at")
    search_fields = ("intent_id", "provider_ref", "user__email", "user__username")
    readonly_fields = (
        "provider_ref",
        "meta_json",
        "error_code",
        "error_message",
        "consumed_at",
        "created_at",
        "updated_at",
    )
    inlines = (ProviderTransactionInline,)
    actions = ("mark_success", "mark_failed", "mark_consumed")

    @admin.action(description="Mark as success")
    def mark_success(self, request, queryset):
        for payment in queryset:
            try:
                services.apply_success(payment, provider_ref=payment.provider_ref or "MANUAL")
            except Exception as exc:  # pragma: no cover - admin convenience
                self.message_user(request, str(exc), level=messages.ERROR)
        self.message_user(request, "پرداخت‌ها با موفقیت ثبت شد.", level=messages.SUCCESS)

    @admin.action(description="Mark as failed")
    def mark_failed(self, request, queryset):
        for payment in queryset:
            try:
                services.apply_fail(payment, code="MANUAL", message="ثبت دستی توسط ادمین.")
            except Exception as exc:  # pragma: no cover - admin convenience
                self.message_user(request, str(exc), level=messages.ERROR)
        self.message_user(request, "وضعیت پرداخت‌ها به ناموفق تغییر کرد.")

    @admin.action(description="Mark as consumed")
    def mark_consumed(self, request, queryset):
        for payment in queryset:
            try:
                services.mark_consumed(payment)
            except Exception as exc:  # pragma: no cover - admin convenience
                self.message_user(request, str(exc), level=messages.ERROR)
        self.message_user(request, "مصرف درآمد ثبت شد.", level=messages.SUCCESS)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("uuid", "payment", "amount", "status", "requested_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("payment__intent_id", "provider_refund_id")


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "scope", "payment", "created_at")
    search_fields = ("key",)
    list_filter = ("scope",)
