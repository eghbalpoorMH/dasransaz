from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.api.views import RequestVerificationCodeView, VerifyCodeView

urlpatterns = [
    path("request-code/", RequestVerificationCodeView.as_view(), name="request-code"),
    path("verify/", VerifyCodeView.as_view(), name="verify-code"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
