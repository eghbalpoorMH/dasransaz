from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Child, PhoneVerification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("username",)
    list_display = ("username", "phone_number", "email", "is_staff", "is_active")
    search_fields = ("username", "phone_number", "first_name", "last_name", "email")
    readonly_fields = ("uuid", "created_at", "updated_at", "date_joined", "last_login")

    fieldsets = (
        ("Credentials", {"fields": ("username", "phone_number", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
        ("Identifiers", {"fields": ("uuid",)}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "phone_number",
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    filter_horizontal = ("groups", "user_permissions")


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "created_at", "expires_at", "is_used")
    search_fields = ("phone_number",)
    list_filter = ("is_used",)


@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "age_years", "created_at")
    search_fields = ("name", "user__username", "user__email")
    list_filter = ("age_years",)
