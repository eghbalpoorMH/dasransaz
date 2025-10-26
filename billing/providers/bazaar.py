from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from .base import BaseProvider


class BazaarIAPProvider(BaseProvider):
    code = "bazaar_iap"

    TOKEN_URL = "https://pardakht.cafebazaar.ir/devapi/v2/auth/token/"
    VALIDATE_URL = "https://pardakht.cafebazaar.ir/devapi/v2/api/validate"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[timezone.datetime] = None

    def init_payment(self, payment, return_url: str, callback_url: str) -> dict[str, Any]:
        return {
            "type": "sdk",
            "payload": {
                "provider": self.code,
                "intent_id": payment.intent_id,
            },
            "hint": "Use Bazaar SDK and call verify endpoint.",
        }

    def handle_callback(self, request) -> dict[str, Any]:  # pragma: no cover - Bazaar has no callbacks
        raise NotImplementedError("Bazaar IAP uses server-side verification only")

    def server_verify(self, payment, **kwargs) -> dict[str, Any]:
        purchase_token = kwargs.get("purchase_token")
        product_id = kwargs.get("product_id")
        order_id = kwargs.get("order_id")
        if not purchase_token or not product_id:
            raise ImproperlyConfigured("purchase_token and product_id are required for Bazaar verification")

        response_data = self._validate_purchase(product_id=product_id, purchase_token=purchase_token)

        purchase_state = response_data.get("status") or response_data.get("purchaseState")
        if purchase_state not in (0, "success"):
            return {
                "status": "failed",
                "error_code": response_data.get("error_code", "TOKEN_VERIFICATION_FAILED"),
                "raw": response_data,
            }

        provider_ref = order_id or response_data.get("orderId") or purchase_token
        return {
            "status": "success",
            "provider_ref": provider_ref,
            "raw": response_data,
        }

    def refund(self, payment, amount: int, reason: str = "") -> dict[str, Any]:
        return {"status": "unsupported"}

    def _get_access_token(self) -> str:
        if self._access_token and self._token_expiry and timezone.now() < self._token_expiry:
            return self._access_token

        client_id = self.config.get("CLIENT_ID")
        client_secret = self.config.get("CLIENT_SECRET")
        refresh_token = self.config.get("REFRESH_TOKEN")
        if not all([client_id, client_secret, refresh_token]):
            raise ImproperlyConfigured("Bazaar provider credentials are not configured")

        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            payload = response.json()

        access_token = payload.get("access_token")
        if not access_token:
            raise ImproperlyConfigured("Bazaar access token response is invalid.")
        expires_in = payload.get("expires_in", 3600)
        self._access_token = access_token
        self._token_expiry = timezone.now() + timedelta(seconds=max(expires_in - 60, 60))
        return access_token

    def _validate_purchase(self, product_id: str, purchase_token: str) -> dict[str, Any]:
        package_name = self.config.get("PACKAGE_NAME")
        if not package_name:
            raise ImproperlyConfigured("Bazaar package name is not configured.")

        access_token = self._get_access_token()
        sandbox = self.config.get("SANDBOX", True)
        url = f"{self.VALIDATE_URL}/{package_name}/inapp/{product_id}/{purchase_token}/"

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"sandbox": str(bool(sandbox)).lower()}
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
