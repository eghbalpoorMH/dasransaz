from __future__ import annotations

from django.urls import path

from .views import (
    BazaarVerifyView,
    IranGatewayCallbackView,
    PaymentInitView,
    PaymentRefundView,
    PaymentStatusView,
)

app_name = "billing"

urlpatterns = [
    path("payments/init/", PaymentInitView.as_view(), name="payment-init"),
    path("payments/iran-gw/callback/", IranGatewayCallbackView.as_view(), name="billing-iran-callback"),
    path("payments/bazaar/verify/", BazaarVerifyView.as_view(), name="billing-bazaar-verify"),
    path("payments/<uuid:payment_id>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("payments/<uuid:payment_id>/refund/", PaymentRefundView.as_view(), name="payment-refund"),
]
