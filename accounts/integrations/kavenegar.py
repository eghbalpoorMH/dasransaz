from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class KavenegarClient:
    """Minimal client for sending OTP codes via Kavenegar."""

    base_url = "https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"

    def __init__(
        self,
        api_key: str,
        sender: Optional[str] = None,
        template: Optional[str] = None,
        *,
        timeout: float = 5.0,
    ):
        self.api_key = api_key
        self.sender = sender
        self.template = template
        self.timeout = timeout

    def send_verification_code(self, receptor: str, code: str) -> None:
        if not self.api_key:
            logger.warning("Kavenegar API key missing; SMS not sent.")
            return

        url = self.base_url.format(api_key=self.api_key)
        payload = {"receptor": receptor, "token": code}
        if self.template:
            payload["template"] = self.template
        if self.sender:
            payload["sender"] = self.sender

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, data=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Failed to send OTP via Kavenegar: %s", exc)
