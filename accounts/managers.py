from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Custom manager for phone based authentication."""

    use_in_migrations = True

    def normalize_phone(self, phone_number: str) -> str:
        if not phone_number:
            raise ValueError("Phone number is required")
        normalized = "".join(filter(str.isdigit, phone_number))
        if not normalized:
            raise ValueError("Phone number must contain digits")
        if normalized.startswith("00"):
            normalized = normalized[2:]
        if not normalized.startswith("0") and not normalized.startswith("98"):
            normalized = f"98{normalized}"
        if normalized.startswith("0"):
            normalized = f"98{normalized[1:]}"
        return f"+{normalized}"

    def _create_user(self, phone_number: str, password: str | None, **extra_fields: Any):
        phone_number = self.normalize_phone(phone_number)
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number: str, password: str | None = None, **extra_fields: Any):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone_number, password or self.make_random_password(), **extra_fields)

    def create_superuser(self, phone_number: str, password: str, **extra_fields: Any):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(phone_number, password, **extra_fields)
