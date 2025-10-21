from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from accounts.api.serializers import (
    PasswordLoginSerializer,
    RequestVerificationSerializer,
    VerificationResponseSerializer,
    VerifyCodeSerializer,
)
from accounts.exceptions import CodeExpiredError, InvalidCodeError
from accounts.services import (
    create_verification_code,
    dispatch_verification_code,
    verify_login_code,
)


class RequestVerificationCodeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RequestVerificationSerializer, responses={204: None})
    def post(self, request, *args, **kwargs):
        serializer = RequestVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        _, code = create_verification_code(phone_number)
        print(code)
        dispatch_verification_code(phone_number, code)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerifyCodeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=VerifyCodeSerializer, responses=VerificationResponseSerializer)
    def post(self, request, *args, **kwargs):
        serializer = VerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        try:
            user, created = verify_login_code(phone, code)
        except (InvalidCodeError, CodeExpiredError) as exc:
            raise ValidationError({"detail": str(exc)})

        response_serializer = VerificationResponseSerializer(_build_login_payload(user, is_new_user=created))
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class PasswordLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordLoginSerializer, responses=VerificationResponseSerializer)
    def post(self, request, *args, **kwargs):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        payload = _build_login_payload(user, is_new_user=False)
        response_serializer = VerificationResponseSerializer(payload)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

def _build_login_payload(user, *, is_new_user: bool) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh["phone_number"] = user.phone_number
    access_token = refresh.access_token
    access_token["phone_number"] = user.phone_number

    return {
        "tokens": {
            "refresh": str(refresh),
            "access": str(access_token),
            "user_id": str(user.pk),
        },
        "is_new_user": is_new_user,
    }
