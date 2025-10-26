from __future__ import annotations

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from . import services
from .models import Scene, Story, StoryProduct


class SceneInline(admin.StackedInline):
    model = Scene
    extra = 0
    fields = ("page_no", "text", "image_url", "voice_url", "timings_json", "annotations_json")
    ordering = ("page_no",)


@admin.register(StoryProduct)
class StoryProductAdmin(admin.ModelAdmin):
    list_display = ("title", "coin_price", "bazaar_sku", "is_active", "display_order", "updated_at")
    list_editable = ("coin_price", "bazaar_sku", "is_active", "display_order")
    search_fields = ("title", "slug", "bazaar_sku")
    list_filter = ("is_active",)
    readonly_fields = ("slug", "created_at", "updated_at")
    fieldsets = (
        (_("Basic info"), {"fields": ("title", "slug", "description", "coin_price", "bazaar_sku")}),
        (_("Presentation"), {"fields": ("features", "display_order", "is_active")}),
    )


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "owner",
        "product",
        "status",
        "visibility",
        "is_hidden",
        "plan_source",
        "published_at",
        "created_at",
    )
    list_filter = ("status", "visibility", "is_hidden", "lang", "reading_level", "product", "created_at")
    search_fields = ("title", "slug", "owner__email", "owner__username")
    readonly_fields = ("published_at", "created_at", "updated_at", "plan_source", "request")
    fieldsets = (
        (_("Basic"), {"fields": ("title", "lang", "reading_level", "summary", "cover_url", "cover_meta")}),
        (
            _("Lifecycle"),
            {
                "fields": (
                    "status",
                    "visibility",
                    "is_hidden",
                    "hidden_reason",
                    "published_at",
                    "slug",
                )
            },
        ),
        (_("Relations"), {"fields": ("owner", "child", "product", "request", "plan_source")}),
    )
    inlines = (SceneInline,)
    actions = ("action_publish", "action_unpublish", "action_hide", "action_unhide", "action_move_draft", "action_archive")

    @admin.action(description=_("Publish selected stories"))
    def action_publish(self, request, queryset):
        for story in queryset:
            try:
                services.publish_story(story, actor=request.user)
            except Exception as exc:  # pragma: no cover - admin convenience
                self.message_user(request, f"{story}: {exc}", level=messages.ERROR)
        self.message_user(request, "داستان‌ها منتشر شدند.", level=messages.SUCCESS)

    @admin.action(description=_("Unpublish selected stories"))
    def action_unpublish(self, request, queryset):
        for story in queryset:
            try:
                services.unpublish_story(story, actor=request.user)
            except Exception as exc:  # pragma: no cover - admin convenience
                self.message_user(request, f"{story}: {exc}", level=messages.ERROR)
        self.message_user(request, "داستان‌ها به حالت آماده بازگشتند.")

    @admin.action(description=_("Hide selected stories"))
    def action_hide(self, request, queryset):
        for story in queryset:
            services.hide_story(story, reason="Admin action", actor=request.user)
        self.message_user(request, "داستان‌ها مخفی شدند.", level=messages.SUCCESS)

    @admin.action(description=_("Unhide selected stories"))
    def action_unhide(self, request, queryset):
        for story in queryset:
            services.unhide_story(story, actor=request.user)
        self.message_user(request, "داستان‌ها نمایش داده خواهند شد.", level=messages.SUCCESS)

    @admin.action(description=_("Move to draft"))
    def action_move_draft(self, request, queryset):
        queryset.update(status=Story.Status.DRAFT, visibility=Story.Visibility.PRIVATE, published_at=None)
        self.message_user(request, "داستان‌ها به حالت پیش‌نویس منتقل شدند.")

    @admin.action(description=_("Archive"))
    def action_archive(self, request, queryset):
        queryset.update(status=Story.Status.ARCHIVED, visibility=Story.Visibility.PRIVATE)
        self.message_user(request, "داستان‌ها بایگانی شدند.")
