from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderCoinRate",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("uuid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.CharField(max_length=50)),
                ("currency", models.CharField(default="IRR", max_length=10)),
                ("base_amount", models.PositiveIntegerField(help_text="Amount in provider currency for one step.")),
                ("coins", models.PositiveIntegerField(help_text="Coins granted per step.")),
                ("is_active", models.BooleanField(default=True)),
                ("note", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "verbose_name": "Provider coin rate",
                "ordering": ("provider", "currency", "base_amount"),
                "unique_together": {("provider", "currency", "base_amount")},
            },
        ),
        migrations.CreateModel(
            name="Wallet",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("uuid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("balance", models.PositiveIntegerField(default=0)),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="wallet", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Wallet",
            },
        ),
        migrations.CreateModel(
            name="WalletTransaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("uuid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "type",
                    models.CharField(
                        choices=[("deposit", "Deposit"), ("withdraw", "Withdraw"), ("adjust", "Adjust")],
                        max_length=10,
                    ),
                ),
                ("coins", models.IntegerField()),
                ("balance_after", models.PositiveIntegerField()),
                ("description", models.CharField(blank=True, max_length=255)),
                (
                    "payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wallet_transactions",
                        to="billing.payment",
                    ),
                ),
                (
                    "wallet",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transactions", to="billing.wallet"),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(fields=("wallet", "created_at"), name="billing_wallet_tx_idx"),
        ),
    ]
