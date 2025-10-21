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


class PasswordLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    default_error_messages = {
        "invalid_credentials": _("مشخصات ورود نادرست است."),
        "inactive": _("این حساب کاربری غیرفعال است."),
    }

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        phone = attrs.get("phone_number") or ""
        password = attrs.get("password") or ""
        normalized_phone = User.objects.normalize_phone(phone)

        try:
            user = User.objects.get(phone_number=normalized_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone_number": [_("کاربری با این شماره یافت نشد.")]})

        if not user.check_password(password):
            raise serializers.ValidationError({"password": [_("رمز عبور اشتباه است.")]})
        if not user.is_active:
            self.fail("inactive")

        attrs["user"] = user
        attrs["phone_number"] = normalized_phone
        return attrs


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user_id = serializers.CharField(read_only=True)


class VerificationResponseSerializer(serializers.Serializer):
    tokens = TokenPairSerializer()
    is_new_user = serializers.BooleanField()
