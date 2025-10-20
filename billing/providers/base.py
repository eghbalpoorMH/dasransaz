from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    code = "base"

    def __init__(self, *, config: dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    def init_payment(self, payment, return_url: str, callback_url: str) -> dict[str, Any]:
        """Initialize a payment and return the action payload."""

    @abstractmethod
    def handle_callback(self, request) -> dict[str, Any]:
        """Process provider callback requests."""

    def server_verify(self, payment, **kwargs) -> dict[str, Any]:
        return {"status": "noop"}

    def refund(self, payment, amount: int, reason: str = "") -> dict[str, Any]:
        return {"status": "unsupported"}
