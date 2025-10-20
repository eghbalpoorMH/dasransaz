from __future__ import annotations

import uuid

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import migrations, models
from django.utils import timezone


def _normalize_phone(phone_number: str) -> str:
    digits = "".join(filter(str.isdigit, phone_number or ""))
    if not digits:
        raise ValueError("Phone number must contain digits")
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits.startswith("0") and not digits.startswith("98"):
        digits = f"98{digits}"
    if digits.startswith("0"):
        digits = f"98{digits[1:]}"
    return f"+{digits}"


def _generate_username(candidate_base: str, taken: set[str]) -> str:
    base = candidate_base or "user"
    username = base
    counter = 0
    while username in taken:
        counter += 1
        username = f"{base}_{counter}"
    taken.add(username)
    return username


def bootstrap_user_identity_fields(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    db_alias = schema_editor.connection.alias
    users = User.objects.using(db_alias).all()

    taken_usernames: set[str] = set(
        value.strip().lower()
        for value in users.exclude(username__isnull=True).values_list("username", flat=True)
        if value
    )
    seen_emails: set[str] = set(
        value.strip().lower()
        for value in users.exclude(email__isnull=True).values_list("email", flat=True)
        if value
    )

    for user in users.iterator():
        updates: dict[str, str | None] = {}

        email_clean = (user.email or "").strip().lower()
        if email_clean and email_clean not in seen_emails:
            updates["email"] = email_clean
            seen_emails.add(email_clean)
        else:
            updates["email"] = None

        phone_raw = (user.phone_number or "").strip()
        normalized_phone = None
        if phone_raw:
            try:
                normalized_phone = _normalize_phone(phone_raw)
                updates["phone_number"] = normalized_phone
            except ValueError:
                updates["phone_number"] = None
        else:
            updates["phone_number"] = None

        username_clean = (user.username or "").strip().lower()
        if username_clean and username_clean not in taken_usernames:
            username_value = username_clean
        else:
            base = (normalized_phone or "").replace("+", "")
            if not base:
                base = f"user_{str(user.pk).replace('-', '')[:16]}"
            username_value = _generate_username(base, taken_usernames)
        taken_usernames.add(username_value)
        updates["username"] = username_value

        updates["uuid"] = user.id
        joined = getattr(user, "date_joined", None)
        created_at = joined or timezone.now()
        updates["created_at"] = created_at
        updates["updated_at"] = timezone.now()

        User.objects.using(db_alias).filter(pk=user.pk).update(**updates)


def bootstrap_phone_verification_fields(apps, schema_editor):
    PhoneVerification = apps.get_model("accounts", "PhoneVerification")
    db_alias = schema_editor.connection.alias
    for verification in PhoneVerification.objects.using(db_alias).only("pk", "created_at"):
        created_at = verification.created_at or timezone.now()
        PhoneVerification.objects.using(db_alias).filter(pk=verification.pk).update(
            updated_at=created_at,
            uuid=uuid.uuid4(),
        )


def noop_reverse(apps, schema_editor):
    """No rollback for data population."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(
                help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                max_length=150,
                null=True,
                unique=True,
                validators=[UnicodeUsernameValidator()],
            ),
        ),
        migrations.AddField(
            model_name="phoneverification",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="phoneverification",
            name="uuid",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.RunPython(bootstrap_user_identity_fields, noop_reverse),
        migrations.RunPython(bootstrap_phone_verification_fields, noop_reverse),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                max_length=150,
                unique=True,
                validators=[UnicodeUsernameValidator()],
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="phone_number",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
    ]
