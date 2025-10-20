from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from story_requests.models import StoryRequest

from .models import Scene, Story
from .signals import story_hidden, story_published, story_unhidden, story_unpublished


@dataclass
class ScenePayload:
    page_no: int
    text: str
    image_url: str | None = None
    voice_url: str | None = None
    timings_json: dict | None = None
    annotations_json: dict | None = None


@transaction.atomic
def create_story_from_request(
    request_obj: StoryRequest,
    *,
    title: str,
    scenes_data: Iterable[dict] | None = None,
) -> Story:
    if hasattr(request_obj, "story") and request_obj.story_id:
        raise ValidationError("برای این درخواست قبلاً داستانی ساخته شده است.")

    scenes_data = list(scenes_data or [])
    story = Story.objects.create(
        request=request_obj,
        owner=request_obj.user,
        child=request_obj.child,
        title=title,
        lang=request_obj.lang,
        reading_level=request_obj.reading_level,
        plan_source=request_obj.plan,
        status=Story.Status.READY,
        visibility=Story.Visibility.PRIVATE,
    )

    if not scenes_data:
        # Ensure at least one empty scene placeholder
        Scene.objects.create(story=story, page_no=1, text="")
    else:
        used_pages: set[int] = set()
        for index, payload in enumerate(scenes_data, start=1):
            requested_page = payload.get("page_no")
            if requested_page:
                if requested_page in used_pages:
                    raise ValidationError("شماره صفحه تکراری است.")
                scene_page = requested_page
            else:
                candidate = index
                while candidate in used_pages:
                    candidate += 1
                scene_page = candidate
            used_pages.add(scene_page)
            Scene.objects.create(
                story=story,
                page_no=scene_page,
                text=payload.get("text", ""),
                image_url=payload.get("image_url"),
                voice_url=payload.get("voice_url"),
                timings_json=payload.get("timings_json", {}),
                annotations_json=payload.get("annotations_json", {}),
            )

    return story


@transaction.atomic
def publish_story(story: Story, *, actor=None) -> Story:
    if story.is_hidden:
        raise ValidationError("داستان مخفی شده است و امکان انتشار ندارد.")
    if story.status not in {Story.Status.READY, Story.Status.PUBLISHED}:
        raise ValidationError("وضعیت داستان برای انتشار مناسب نیست.")
    story.status = Story.Status.PUBLISHED
    story.visibility = Story.Visibility.PUBLIC
    story.published_at = timezone.now()
    story.save(update_fields=["status", "visibility", "published_at", "updated_at"])
    story_published.send(sender=Story, story=story, actor=actor)
    return story


@transaction.atomic
def unpublish_story(story: Story, *, actor=None) -> Story:
    if story.status != Story.Status.PUBLISHED:
        raise ValidationError("داستان در حالت انتشار نیست.")
    story.status = Story.Status.READY
    story.visibility = Story.Visibility.PRIVATE
    story.published_at = None
    story.save(update_fields=["status", "visibility", "published_at", "updated_at"])
    story_unpublished.send(sender=Story, story=story, actor=actor)
    return story


@transaction.atomic
def hide_story(story: Story, *, reason: str = "", actor=None) -> Story:
    if story.is_hidden and story.hidden_reason == reason:
        return story
    story.is_hidden = True
    story.hidden_reason = reason or None
    story.save(update_fields=["is_hidden", "hidden_reason", "updated_at"])
    story_hidden.send(sender=Story, story=story, actor=actor)
    return story


@transaction.atomic
def unhide_story(story: Story, *, actor=None) -> Story:
    if not story.is_hidden:
        return story
    story.is_hidden = False
    story.hidden_reason = None
    story.save(update_fields=["is_hidden", "hidden_reason", "updated_at"])
    story_unhidden.send(sender=Story, story=story, actor=actor)
    return story


@transaction.atomic
def reorder_scenes(story: Story, order_payload: Sequence[dict[str, int]]) -> Story:
    if not order_payload:
        raise ValidationError("آرایش صفحات خالی است.")

    page_numbers = [item.get("page_no") for item in order_payload]
    if len(page_numbers) != len(set(page_numbers)):
        raise ValidationError("شماره صفحات تکراری است.")

    scenes_map = {scene.id: scene for scene in story.scenes.select_for_update()}
    for item in order_payload:
        scene_id = item.get("id")
        if scene_id not in scenes_map:
            raise ValidationError(f"صحنه با شناسه {scene_id} یافت نشد.")
        scene = scenes_map[scene_id]
        scene.page_no = item.get("page_no", scene.page_no)
        scene.save(update_fields=["page_no", "updated_at"])

    return story


@transaction.atomic
def upsert_scenes(story: Story, scenes_payload: Sequence[dict]) -> Story:
    if not scenes_payload:
        raise ValidationError("لیست صحنه‌ها خالی است.")

    existing_scenes = {scene.id: scene for scene in story.scenes.select_for_update()}
    seen_page_numbers: set[int] = set()
    retained_ids: set[int] = set()

    for index, payload in enumerate(scenes_payload, start=1):
        scene_id = payload.get("id")
        page_no = payload.get("page_no") or index
        if page_no in seen_page_numbers:
            raise ValidationError("شماره صفحه تکراری است.")
        seen_page_numbers.add(page_no)

        defaults = {
            "page_no": page_no,
            "text": payload.get("text", ""),
            "image_url": payload.get("image_url"),
            "voice_url": payload.get("voice_url"),
            "timings_json": payload.get("timings_json", {}),
            "annotations_json": payload.get("annotations_json", {}),
        }

        if scene_id and scene_id in existing_scenes:
            scene = existing_scenes[scene_id]
            for field, value in defaults.items():
                setattr(scene, field, value)
            scene.save(update_fields=["page_no", "text", "image_url", "voice_url", "timings_json", "annotations_json", "updated_at"])
            retained_ids.add(scene_id)
        else:
            scene = Scene.objects.create(story=story, **defaults)
            retained_ids.add(scene.id)

    # delete removed scenes
    scenes_to_delete = [scene_id for scene_id in existing_scenes if scene_id not in retained_ids]
    if scenes_to_delete:
        Scene.objects.filter(id__in=scenes_to_delete).delete()

    return story
