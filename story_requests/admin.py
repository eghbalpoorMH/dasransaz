from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.shortcuts import redirect

from .models import RequestTransition, StoryRequest
from .services import transition


class RequestTransitionInline(admin.TabularInline):
    model = RequestTransition
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "actor", "note", "created_at")
    ordering = ("-created_at",)


class CancelActionForm(ActionForm):
    cancellation_reason = forms.CharField(label="دلیل لغو", required=False)


class EditorWorkspaceForm(forms.Form):
    prompt = forms.CharField(
        label="یادداشت برای مدل هوش مصنوعی",
        widget=forms.Textarea(attrs={"rows": 6}),
        required=False,
    )
    target_status = forms.ChoiceField(
        label="وضعیت پس از ایجاد داستان",
        choices=(
            (StoryRequest.Status.REVIEW_PENDING, "Ready for review"),
            (StoryRequest.Status.READY_FOR_USER, "Ready for user"),
        ),
    )


@admin.register(StoryRequest)
class StoryRequestAdmin(admin.ModelAdmin):
    list_display = ("public_id", "user", "child", "product", "plan", "status", "queue_priority", "created_at")
    list_filter = ("status", "plan", "product", "lang", "reading_level", "created_at")
    search_fields = ("user__username", "user__email", "child__name", "theme")
    ordering = ("queue_priority", "created_at")
    readonly_fields = ("position_hint", "payment", "created_at", "updated_at")
    inlines = (RequestTransitionInline,)
    actions = ("move_to_in_progress", "mark_review_pending", "mark_ready_for_user", "cancel_with_reason")
    action_form = CancelActionForm

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/workspace/",
                self.admin_site.admin_view(self.editor_workspace_view),
                name="requests_storyrequest_workspace",
            )
        ]
        return custom_urls + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["workspace_url"] = reverse(
            "admin:requests_storyrequest_workspace", args=[object_id]
        )
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    @admin.display(description="Move to IN_PROGRESS")
    def move_to_in_progress(self, request, queryset):
        self._bulk_transition(request, queryset, StoryRequest.Status.IN_PROGRESS, "در حال پردازش شد.")

    @admin.display(description="Mark REVIEW_PENDING")
    def mark_review_pending(self, request, queryset):
        self._bulk_transition(
            request, queryset, StoryRequest.Status.REVIEW_PENDING, "در انتظار بازبینی."
        )

    @admin.display(description="Mark READY_FOR_USER")
    def mark_ready_for_user(self, request, queryset):
        self._bulk_transition(
            request, queryset, StoryRequest.Status.READY_FOR_USER, "آماده برای کاربر."
        )

    @admin.display(description="Cancel with reason…")
    def cancel_with_reason(self, request, queryset):
        reason = (request.POST.get("cancellation_reason") or "").strip()
        self._bulk_transition(
            request,
            queryset,
            StoryRequest.Status.CANCELED,
            reason or "لغو توسط ادمین.",
        )

    def _bulk_transition(self, request, queryset, target_status, note):
        success = 0
        for story_request in queryset:
            try:
                transition(story_request, target_status, actor=request.user, note=note)
                success += 1
            except ValidationError as exc:
                self.message_user(request, f"{story_request.public_id}: {exc}", level=messages.ERROR)

        if success:
            self.message_user(
                request,
                f"{success} درخواست با موفقیت به {target_status} به‌روزرسانی شد.",
                level=messages.SUCCESS,
            )

    def editor_workspace_view(self, request, object_id):
        story_request = self.get_object(request, object_id)
        if story_request is None:
            self.message_user(request, "درخواست پیدا نشد.", level=messages.ERROR)
            return redirect("admin:requests_storyrequest_changelist")

        form = EditorWorkspaceForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            prompt = form.cleaned_data["prompt"]
            target_status = form.cleaned_data["target_status"]
            meta = story_request.meta_json or {}
            meta["editor_prompt"] = prompt
            story_request.meta_json = meta
            story_request.save(update_fields=["meta_json", "updated_at"])
            try:
                transition(
                    story_request,
                    target_status,
                    actor=request.user,
                    note="ایجاد داستان از طریق محیط ویرایشگر.",
                )
                self.message_user(request, "وضعیت درخواست به‌روزرسانی شد.", level=messages.SUCCESS)
                return redirect("admin:requests_storyrequest_change", story_request.pk)
            except ValidationError as exc:
                self.message_user(request, str(exc), level=messages.ERROR)

        context = {
            "opts": self.model._meta,
            "story_request": story_request,
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/requests/storyrequest/editor_workspace.html",
            context,
        )
