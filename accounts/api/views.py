from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.api.serializers import (
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

    def post(self, request, *args, **kwargs):
        serializer = RequestVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone_number"]
        _, code = create_verification_code(phone_number)
        dispatch_verification_code(phone_number, code)
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerifyCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = VerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        try:
            user, created = verify_login_code(phone, code)
        except (InvalidCodeError, CodeExpiredError) as exc:
            raise ValidationError({"detail": str(exc)})

        refresh = RefreshToken.for_user(user)
        refresh["phone_number"] = user.phone_number
        access_token = refresh.access_token
        access_token["phone_number"] = user.phone_number

        response_serializer = VerificationResponseSerializer(
            {
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(access_token),
                    "user_id": str(user.pk),
                },
                "is_new_user": created,
            }
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
