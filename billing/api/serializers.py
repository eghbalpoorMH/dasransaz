from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework import serializers

from billing.models import Payment


class PaymentInitSerializer(serializers.Serializer):
    intent_id = serializers.CharField(max_length=64)
    provider = serializers.CharField(max_length=50, required=False)
    amount = serializers.IntegerField(min_value=1)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    return_url = serializers.URLField(required=False, allow_blank=True)

    def validate_provider(self, value: str) -> str:
        if value and value not in settings.BILLING.get("PROVIDERS", {}):
            raise serializers.ValidationError("ارائه‌دهندهٔ پرداخت معتبر نیست.")
        return value


class IranGatewayCallbackSerializer(serializers.Serializer):
    intent_id = serializers.CharField(max_length=64)
    status = serializers.ChoiceField(choices=["success", "failed"])
    provider_ref = serializers.CharField(max_length=128, required=False, allow_blank=True)
    raw = serializers.JSONField(default=dict)
    error_code = serializers.CharField(max_length=64, required=False, allow_blank=True)
    error_message = serializers.CharField(required=False, allow_blank=True)


class BazaarVerifySerializer(serializers.Serializer):
    intent_id = serializers.CharField(max_length=64)
    product_id = serializers.CharField(max_length=100)
    purchase_token = serializers.CharField(max_length=200)
    order_id = serializers.CharField(max_length=200, required=False, allow_blank=True)


class WalletPaymentSerializer(serializers.Serializer):
    intent_id = serializers.CharField(max_length=64)
    note = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "uuid",
            "status",
            "provider",
            "amount",
            "currency",
            "intent_id",
            "provider_ref",
            "error_code",
            "error_message",
            "consumed_at",
        )
        read_only_fields = fields


class RefundRequestSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["full", "partial"])
    amount = serializers.IntegerField(required=False, min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        mode = attrs.get("mode")
        amount = attrs.get("amount")
        if mode == "partial" and amount is None:
            raise serializers.ValidationError({"amount": "لطفاً مبلغ بازگشت جزئی را مشخص کنید."})
        return attrs
