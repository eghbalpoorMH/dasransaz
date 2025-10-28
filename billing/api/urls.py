from __future__ import annotations

from django.urls import path

from .views import (
    BazaarVerifyView,
    IranGatewayCallbackView,
    PaymentInitView,
    PaymentRefundView,
    PaymentStatusView,
    WalletInfoView,
    WalletPaymentView,
)

app_name = "billing"

urlpatterns = [
    path("payments/init/", PaymentInitView.as_view(), name="payment-init"),
    path("payments/iran-gw/callback/", IranGatewayCallbackView.as_view(), name="billing-iran-callback"),
    path("payments/bazaar/verify/", BazaarVerifyView.as_view(), name="billing-bazaar-verify"),
    path("payments/wallet/", WalletInfoView.as_view(), name="wallet-info"),
    path("payments/wallet/pay/", WalletPaymentView.as_view(), name="wallet-pay"),
    path("payments/<uuid:payment_id>/status/", PaymentStatusView.as_view(), name="payment-status"),
    path("payments/<uuid:payment_id>/refund/", PaymentRefundView.as_view(), name="payment-refund"),
]
