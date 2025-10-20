from __future__ import annotations


class BillingError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class PaymentAlreadySucceeded(BillingError):
    def __init__(self):
        super().__init__("PAYMENT_ALREADY_SUCCEEDED", "این سفارش پیش‌تر با موفقیت پرداخت شده است.")


class InvalidProvider(BillingError):
    def __init__(self):
        super().__init__("INVALID_PROVIDER", "ارائه‌دهندهٔ پرداخت معتبر نیست.")


class TokenVerificationFailed(BillingError):
    def __init__(self, message: str | None = None):
        super().__init__("TOKEN_VERIFICATION_FAILED", message or "تأیید خرید ناموفق بود.")


class AmountMismatch(BillingError):
    def __init__(self):
        super().__init__("AMOUNT_MISMATCH", "مبلغ پرداخت با سفارش هم‌خوانی ندارد.")


class ProviderUnavailable(BillingError):
    def __init__(self):
        super().__init__("PROVIDER_UNAVAILABLE", "درگاه پرداخت موقتاً در دسترس نیست.")


class RefundNotAllowed(BillingError):
    def __init__(self):
        super().__init__("REFUND_NOT_ALLOWED", "امکان بازگشت وجه در این مرحله وجود ندارد.")


class StoryRequestNotFound(BillingError):
    def __init__(self):
        super().__init__("REQUEST_NOT_FOUND", "درخواست داستانی با این شناسه پیدا نشد.")


class PaymentNotAllowed(BillingError):
    def __init__(self, message: str | None = None):
        super().__init__("PAYMENT_NOT_ALLOWED", message or "در این مرحله امکان پرداخت وجود ندارد.")


class PermissionDeniedBilling(BillingError):
    def __init__(self):
        super().__init__("PERMISSION_DENIED", "دسترسی مجاز نیست.")
