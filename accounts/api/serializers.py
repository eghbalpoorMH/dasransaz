from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import User


class RequestVerificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value: str) -> str:
        try:
            return User.objects.normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class VerifyCodeSerializer(RequestVerificationSerializer):
    code = serializers.CharField(max_length=10)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user_id = serializers.CharField(read_only=True)


class VerificationResponseSerializer(serializers.Serializer):
    tokens = TokenPairSerializer()
    is_new_user = serializers.BooleanField()
