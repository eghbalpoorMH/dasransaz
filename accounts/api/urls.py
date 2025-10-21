from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.api.views import PasswordLoginView, RequestVerificationCodeView, VerifyCodeView

urlpatterns = [
    path("request-code/", RequestVerificationCodeView.as_view(), name="request-code"),
    path("verify/", VerifyCodeView.as_view(), name="verify-code"),
    path("password-login/", PasswordLoginView.as_view(), name="password-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
