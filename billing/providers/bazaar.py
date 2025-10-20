from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import BaseProvider


class BazaarIAPProvider(BaseProvider):
    code = "bazaar_iap"

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

        response_data = self._request(
            "https://pardakht.cafebazaar.ir/devapi/v2/api/validate",  # placeholder endpoint
            {
                "purchaseToken": purchase_token,
                "sku": product_id,
                "packageName": self.config.get("PACKAGE_NAME"),
                "sandbox": self.config.get("SANDBOX", True),
            },
        )

        status = response_data.get("status", "failed")
        if status != "success":
            return {
                "status": "failed",
                "error_code": response_data.get("error_code", "TOKEN_VERIFICATION_FAILED"),
                "raw": response_data,
            }

        provider_ref = order_id or response_data.get("order_id") or purchase_token
        return {
            "status": "success",
            "provider_ref": provider_ref,
            "raw": response_data,
        }

    def refund(self, payment, amount: int, reason: str = "") -> dict[str, Any]:
        return {"status": "unsupported"}

    def _request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        client_id = self.config.get("CLIENT_ID")
        client_secret = self.config.get("CLIENT_SECRET")
        if not client_id or not client_secret:
            raise ImproperlyConfigured("Bazaar provider credentials are not configured")

        headers = {"Authorization": f"Basic {client_id}:{client_secret}"}
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

