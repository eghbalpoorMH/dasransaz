from __future__ import annotations

import logging
import secrets
from typing import Tuple

from django.conf import settings
from django.db import transaction

from accounts.exceptions import CodeExpiredError, InvalidCodeError
from accounts.integrations.kavenegar import KavenegarClient
from accounts.models import PhoneVerification, User

logger = logging.getLogger(__name__)

NUMERIC_ALPHABET = "0123456789"


def generate_numeric_code(length: int | None = None) -> str:
    code_length = length or settings.AUTH_VERIFICATION_CODE_LENGTH
    return "".join(secrets.choice(NUMERIC_ALPHABET) for _ in range(code_length))


@transaction.atomic
def create_verification_code(phone_number: str) -> Tuple[PhoneVerification, str]:
    normalized_phone = User.objects.normalize_phone(phone_number)
    PhoneVerification.objects.filter(phone_number=normalized_phone, is_used=False).update(is_used=True)
    raw_code = generate_numeric_code()
    verification = PhoneVerification.create_code(normalized_phone, raw_code)
    logger.debug("Generated verification code for %s", normalized_phone)
    return verification, raw_code


def dispatch_verification_code(phone_number: str, code: str) -> None:
    client = KavenegarClient(
        api_key=settings.KAVENEGAR_API_KEY or "",
        sender=settings.KAVENEGAR_SENDER,
        template=settings.KAVENEGAR_TEMPLATE,
    )
    client.send_verification_code(phone_number, code)
    if not settings.KAVENEGAR_API_KEY:
        logger.info("Kavenegar API key missing, code %s logged instead for %s", code, phone_number)


def verify_login_code(phone_number: str, code: str) -> tuple[User, bool]:
    normalized_phone = User.objects.normalize_phone(phone_number)
    verification = (
        PhoneVerification.objects.filter(phone_number=normalized_phone, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if verification is None:
        raise InvalidCodeError("No active verification code found.")
    if verification.is_expired:
        verification.mark_used()
        raise CodeExpiredError("Verification code expired.")
    if not verification.verify(code):
        raise InvalidCodeError("Verification code is invalid.")

    verification.mark_used()
    user, created = User.objects.get_or_create_by_phone(normalized_phone)
    if created:
        logger.info("Created new user with phone %s", normalized_phone)
    return user, created
