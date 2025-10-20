from __future__ import annotations

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import Child
from stories.models import Scene, Story


class ChildSummarySerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()

    class Meta:
        model = Child
        fields = ("id", "name", "age")

    def get_age(self, obj: Child) -> Any:
        return obj.age


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = (
            "id",
            "page_no",
            "text",
            "image_url",
            "voice_url",
            "timings_json",
            "annotations_json",
        )
        read_only_fields = fields


class SceneWriteSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    page_no = serializers.IntegerField(required=False, min_value=1)
    text = serializers.CharField()
    image_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    voice_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    timings_json = serializers.DictField(required=False)
    annotations_json = serializers.DictField(required=False)


class StoryListSerializer(serializers.ModelSerializer):
    scenes_count = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = (
            "id",
            "slug",
            "title",
            "cover_url",
            "lang",
            "reading_level",
            "status",
            "visibility",
            "published_at",
            "plan_source",
            "scenes_count",
        )
        read_only_fields = fields

    def get_scenes_count(self, obj: Story) -> int:
        return getattr(obj, "scenes_count", obj.scenes.count())


class StoryDetailSerializer(StoryListSerializer):
    child = ChildSummarySerializer(read_only=True)
    scenes = serializers.SerializerMethodField()
    hidden_reason = serializers.SerializerMethodField()

    class Meta(StoryListSerializer.Meta):
        fields = StoryListSerializer.Meta.fields + (
            "summary",
            "cover_meta",
            "is_hidden",
            "hidden_reason",
            "child",
            "scenes",
        )

    def get_hidden_reason(self, obj: Story) -> str | None:
        request = self.context.get("request")
        if request and request.user and request.user.is_staff:
            return obj.hidden_reason
        return None

    def get_scenes(self, obj: Story):
        include = self.context.get("include_scenes")
        if not include:
            return None
        serializer = SceneSerializer(obj.scenes.order_by("page_no"), many=True)
        return serializer.data

    def to_representation(self, instance: Story):
        data = super().to_representation(instance)
        if data.get("scenes") is None:
            data.pop("scenes", None)
        request = self.context.get("request")
        if not request or not request.user or (not request.user.is_staff and instance.owner_id != request.user.id):
            data.pop("hidden_reason", None)
            data.pop("plan_source", None)
        return data


class PublicStoryListSerializer(serializers.ModelSerializer):
    scenes_count = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = (
            "slug",
            "title",
            "summary",
            "cover_url",
            "lang",
            "reading_level",
            "published_at",
            "scenes_count",
        )
        read_only_fields = fields

    def get_scenes_count(self, obj: Story) -> int:
        return getattr(obj, "scenes_count", obj.scenes.count())


class PublicStoryDetailSerializer(PublicStoryListSerializer):
    scenes = serializers.SerializerMethodField()

    class Meta(PublicStoryListSerializer.Meta):
        fields = PublicStoryListSerializer.Meta.fields + ("scenes",)

    def get_scenes(self, obj: Story):
        include = self.context.get("include_scenes")
        if not include:
            return None
        serializer = SceneSerializer(obj.scenes.order_by("page_no"), many=True)
        return serializer.data

    def to_representation(self, instance: Story):
        data = super().to_representation(instance)
        if data.get("scenes") is None:
            data.pop("scenes", None)
        return data


class StoryFromRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=180)
    scenes = SceneWriteSerializer(many=True, required=False)


class StoryScenesBulkSerializer(serializers.Serializer):
    scenes = SceneWriteSerializer(many=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        pages = [scene.get("page_no") for scene in attrs["scenes"] if scene.get("page_no") is not None]
        if len(pages) != len(set(pages)):
            raise serializers.ValidationError("شماره صفحات نباید تکراری باشد.")
        return attrs
