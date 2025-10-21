from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.utils.crypto import get_random_string


class UserManager(BaseUserManager):
    """Custom manager supporting username and phone based flows."""

    use_in_migrations = True

    def normalize_username(self, username: str) -> str:
        if not username:
            raise ValueError("Username is required")
        return username.strip().lower()

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

    def generate_username_from_phone(self, phone_number: str, *, exclude_pk: Any | None = None) -> str:
        normalized_phone = self.normalize_phone(phone_number)
        base_username = normalized_phone.replace("+", "")
        candidate = base_username
        suffix = 0
        queryset = self.get_queryset()
        if exclude_pk:
            queryset = queryset.exclude(pk=exclude_pk)
        while queryset.filter(username=candidate).exists():
            suffix += 1
            candidate = f"{base_username}_{suffix}"
        return candidate

    def _generate_random_password(self, length: int = 12) -> str:
        return get_random_string(length)

    def _prepare_fields(self, **extra_fields: Any) -> dict[str, Any]:
        fields = extra_fields.copy()
        email = fields.get("email")
        if email:
            fields["email"] = self.normalize_email(email)
        else:
            fields["email"] = None
        phone_number = fields.get("phone_number")
        if phone_number:
            fields["phone_number"] = self.normalize_phone(phone_number)
        else:
            fields["phone_number"] = None
        return fields

    def _create_user(self, username: str, password: str | None, **extra_fields: Any):
        username = self.normalize_username(username)
        fields = self._prepare_fields(**extra_fields)
        user = self.model(username=username, **fields)
        password_to_set = password or self.make_random_password()
        user.set_password(password_to_set)
        user.save(using=self._db)
        return user

    def create_user(self, username: str, password: str | None = None, **extra_fields: Any):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, password, **extra_fields)

    def create_superuser(self, username: str, password: str, **extra_fields: Any):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        if extra_fields.get("email") is None:
            raise ValueError("Superuser must have an email address.")
        if extra_fields.get("phone_number") is None:
            raise ValueError("Superuser must have a phone number.")

        return self._create_user(username, password, **extra_fields)

    def get_or_create_by_phone(self, phone_number: str, **extra_fields: Any):
        normalized_phone = self.normalize_phone(phone_number)
        extra_copy = extra_fields.copy()
        explicit_username = extra_copy.pop("username", None)
        explicit_password = extra_copy.pop("password", None)
        prepared_fields = self._prepare_fields(**extra_copy)

        try:
            user = self.get(phone_number=normalized_phone)
        except self.model.DoesNotExist:
            username = explicit_username or self.generate_username_from_phone(normalized_phone, exclude_pk=None)
            password = explicit_password or self._generate_random_password()
            fields = {**prepared_fields, "phone_number": normalized_phone}
            user = self._create_user(username, password, **fields)
            return user, True

        update_fields: list[str] = []
        for field, value in prepared_fields.items():
            if value is not None and getattr(user, field) != value:
                setattr(user, field, value)
                update_fields.append(field)

        if explicit_password:
            user.set_password(explicit_password)
            update_fields.append("password")

        if update_fields:
            update_fields.append("updated_at")
            user.save(update_fields=update_fields)

        return user, False
