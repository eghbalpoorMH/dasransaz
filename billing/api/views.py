from __future__ import annotations

from urllib.parse import urlencode

from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import services
from billing.exceptions import BillingError, PaymentAlreadySucceeded
from billing.models import Payment, Wallet
from billing.permissions import IsStaffUser

from .serializers import (
    BazaarVerifySerializer,
    IranGatewayCallbackSerializer,
    PaymentInitSerializer,
    PaymentStatusSerializer,
    RefundRequestSerializer,
    WalletPaymentSerializer,
)


class PaymentInitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PaymentInitSerializer,
        responses={
            201: OpenApiResponse(
                response=None,
                description="Payment initialized",
                examples=[
                    OpenApiExample(
                        "Redirect",
                        value={
                            "payment_id": "60b9f4e2-7b2b-4b7a-9a73-5f5f70111111",
                            "status": "pending",
                            "provider": "iran_gw",
                            "action": {"type": "redirect", "url": "https://bank.example/redirect"},
                        },
                    )
                ],
            )
        },
    )
    def post(self, request):
        serializer = PaymentInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        idempotency_key = request.headers.get("Idempotency-Key")
        callback_url = request.build_absolute_uri(reverse("billing:billing-iran-callback"))
        return_url = serializer.validated_data.get("return_url") or request.build_absolute_uri("/")

        try:
            action = services.create_payment(
                intent_id=serializer.validated_data["intent_id"],
                user=request.user,
                provider=serializer.validated_data.get("provider"),
                amount=serializer.validated_data["amount"],
                description=serializer.validated_data.get("description"),
                idempotency_key=idempotency_key,
                return_url=return_url,
                callback_url=callback_url,
                metadata={},
            )
        except PaymentAlreadySucceeded as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=status.HTTP_409_CONFLICT)
        except BillingError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "payment_id": str(action.payment.uuid),
                "status": action.payment.status,
                "provider": action.payment.provider,
                "action": action.action,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class IranGatewayCallbackView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description="Callback processed.")},
    )
    def post(self, request, *args, **kwargs):
        provider = services.get_provider_instance("iran_gw")
        data = provider.handle_callback(request)
        serializer = IranGatewayCallbackSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(intent_id=serializer.validated_data["intent_id"], provider="iran_gw")
                .order_by("-created_at")
                .first()
            )

            if not payment:
                return Response({"detail": "پرداخت یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

            if serializer.validated_data["status"] == "success":
                services.apply_success(
                    payment,
                    provider_ref=serializer.validated_data.get("provider_ref") or "",
                    raw=data.get("raw"),
                )
                payment_status = payment.status
            else:
                services.apply_fail(
                    payment,
                    code=serializer.validated_data.get("error_code") or "UNKNOWN",
                    message=serializer.validated_data.get("error_message") or "پرداخت ناموفق بود.",
                    raw=data.get("raw"),
                )
                payment_status = payment.status

        redirect_url = payment.meta_json.get("return_url") if payment.meta_json else None
        if redirect_url:
            params = urlencode({"status": payment_status, "intent_id": payment.intent_id})
            return HttpResponseRedirect(f"{redirect_url}?{params}")

        return Response({"status": payment_status, "intent_id": payment.intent_id})


class BazaarVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BazaarVerifySerializer,
        responses={200: OpenApiResponse(description="Token verification result.")},
    )
    def post(self, request, *args, **kwargs):
        serializer = BazaarVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            payment = (
                Payment.objects.select_for_update()
                .filter(intent_id=serializer.validated_data["intent_id"], provider="bazaar_iap")
                .order_by("-created_at")
                .first()
            )

            if not payment:
                return Response({"detail": "پرداخت یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

            story_request = payment.story_requests.select_related("product").first()
            expected_sku = None
            if story_request and story_request.product:
                expected_sku = (story_request.product.bazaar_sku or "").strip()
            provided_sku = serializer.validated_data["product_id"].strip()
            if expected_sku and expected_sku.lower() != provided_sku.lower():
                return Response({"detail": "شناسه محصول معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)

            provider = services.get_provider_instance("bazaar_iap")
            result = provider.server_verify(payment, **serializer.validated_data)

            if result.get("status") == "success":
                services.apply_success(
                    payment,
                    provider_ref=result.get("provider_ref") or serializer.validated_data.get("purchase_token"),
                    raw=result.get("raw"),
                )
            else:
                services.apply_fail(
                    payment,
                    code=result.get("error_code", "TOKEN_VERIFICATION_FAILED"),
                    message=result.get("message", "تأیید خرید ناموفق بود."),
                    raw=result.get("raw"),
                )

        return Response({"status": payment.status, "intent_id": payment.intent_id})


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PaymentStatusSerializer)
    def get(self, request, payment_id: str):
        try:
            payment = Payment.objects.get(uuid=payment_id)
        except Payment.DoesNotExist:
            return Response({"detail": "پرداخت یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        try:
            payload = services.get_status(payment, user=request.user)
        except BillingError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=status.HTTP_403_FORBIDDEN)

        serializer = PaymentStatusSerializer(payment)
        data = serializer.data
        data["id"] = data.pop("uuid")
        return Response(data)


class PaymentRefundView(APIView):
    permission_classes = [IsAuthenticated, IsStaffUser]

    @extend_schema(request=RefundRequestSerializer, responses={200: OpenApiResponse(description="Refund processed.")})
    def post(self, request, payment_id: str):
        try:
            payment = Payment.objects.get(uuid=payment_id)
        except Payment.DoesNotExist:
            return Response({"detail": "پرداخت یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            if serializer.validated_data["mode"] == "full":
                refund = services.refund_full(payment, reason=serializer.validated_data.get("reason", ""))
            else:
                refund = services.refund_partial(
                    payment,
                    amount=serializer.validated_data.get("amount", 0),
                    reason=serializer.validated_data.get("reason", ""),
                )
        except BillingError as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "payment_id": str(payment.uuid),
                "refund_id": str(refund.uuid),
                "status": refund.status,
                "amount": refund.amount,
            },
            status=status.HTTP_200_OK,
        )


class WalletInfoView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Wallet balance retrieved.")})
    def get(self, request, *args, **kwargs):
        wallet = Wallet.objects.filter(user=request.user).first()
        balance = wallet.balance if wallet else 0
        return Response({"balance": balance})


class WalletPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=WalletPaymentSerializer, responses={200: OpenApiResponse(description="Wallet payment processed.")})
    def post(self, request, *args, **kwargs):
        serializer = WalletPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = services.pay_with_wallet(
                intent_id=serializer.validated_data["intent_id"],
                user=request.user,
                note=serializer.validated_data.get("note") or "پرداخت با کیف پول انجام شد.",
                description=serializer.validated_data.get("description"),
            )
        except PaymentAlreadySucceeded as exc:
            return Response({"code": exc.code, "detail": exc.message}, status=status.HTTP_409_CONFLICT)
        except BillingError as exc:
            status_code = status.HTTP_400_BAD_REQUEST
            if exc.code == "PERMISSION_DENIED":
                status_code = status.HTTP_403_FORBIDDEN
            return Response({"code": exc.code, "detail": exc.message}, status=status_code)

        return Response(
            {
                "payment_id": str(result.payment.uuid),
                "status": result.payment.status,
                "intent_id": result.payment.intent_id,
                "wallet_balance": result.wallet_balance,
                "coins_spent": result.coins_spent,
            },
            status=status.HTTP_200_OK,
        )
