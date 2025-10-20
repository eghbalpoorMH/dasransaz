from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from accounts.models import Child
from story_requests.services import (
    MAX_FREE_REQUESTS_PER_DAY,
    MAX_OPEN_REQUESTS,
    calc_position,
    enqueue_request,
)
from django.urls import reverse

from .models import RequestTransition, StoryRequest


class CharacterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    role = serializers.CharField(max_length=50)
    age = serializers.IntegerField(required=False, min_value=0)
    traits = serializers.ListField(child=serializers.CharField(max_length=50), required=False)


class ChildSummarySerializer(serializers.ModelSerializer):
    age = serializers.SerializerMethodField()

    class Meta:
        model = Child
        fields = ("id", "name", "age")

    def get_age(self, obj: Child) -> Any:
        return obj.age


class StoryRequestCreateSerializer(serializers.ModelSerializer):
    child_id = serializers.PrimaryKeyRelatedField(
        queryset=Child.objects.all(), source="child", required=False, allow_null=True
    )
    characters = CharacterSerializer(many=True, required=False)

    class Meta:
        model = StoryRequest
        fields = (
            "child_id",
            "lang",
            "reading_level",
            "theme",
            "prompt_note",
            "plan",
            "characters",
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context["request"]
        user = request.user
        plan = attrs.get("plan", StoryRequest.Plan.FREE)

        open_requests_count = StoryRequest.objects.filter(
            user=user, status__in=StoryRequest.OPEN_STATUSES
        ).count()
        if open_requests_count >= MAX_OPEN_REQUESTS:
            raise serializers.ValidationError(
                {"non_field_errors": ["شما بیش از حد مجاز درخواست باز دارید. لطفاً منتظر بمانید."]}
            )

        if plan == StoryRequest.Plan.FREE:
            cutoff = timezone.now() - timedelta(days=1)
            recent_free_count = StoryRequest.objects.filter(
                user=user,
                plan=StoryRequest.Plan.FREE,
                created_at__gte=cutoff,
            ).count()
            if recent_free_count >= MAX_FREE_REQUESTS_PER_DAY:
                raise serializers.ValidationError(
                    {
                        "plan": [
                            "در ۲۴ ساعت گذشته بیش از حد مجاز درخواست رایگان ثبت کرده‌اید."
                        ]
                    }
                )

        return attrs

    def create(self, validated_data: dict[str, Any]) -> StoryRequest:
        characters = validated_data.pop("characters", [])
        user = self.context["request"].user

        story_request = StoryRequest.objects.create(
            user=user,
            characters_json=characters,
            **validated_data,
        )
        enqueue_request(story_request, actor=user)
        story_request.refresh_from_db()
        return story_request


class StoryRequestListSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="public_id", read_only=True)
    position = serializers.SerializerMethodField()
    child = serializers.SerializerMethodField()

    class Meta:
        model = StoryRequest
        fields = ("id", "status", "plan", "theme", "created_at", "position", "child")
        read_only_fields = fields

    def get_position(self, obj: StoryRequest) -> int:
        return calc_position(obj)

    def get_child(self, obj: StoryRequest) -> Any:
        if not obj.child:
            return None
        return ChildSummarySerializer(obj.child).data


class StoryRequestDetailSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="public_id", read_only=True)
    position = serializers.SerializerMethodField()
    queue_type = serializers.SerializerMethodField()
    characters = serializers.SerializerMethodField()
    child = serializers.SerializerMethodField()
    payment_init_url = serializers.SerializerMethodField()

    class Meta:
        model = StoryRequest
        fields = (
            "id",
            "status",
            "plan",
            "theme",
            "prompt_note",
            "lang",
            "reading_level",
            "created_at",
            "updated_at",
            "queue_type",
            "position",
            "characters",
            "child",
            "payment_init_url",
        )
        read_only_fields = fields

    def get_position(self, obj: StoryRequest) -> int:
        return calc_position(obj)

    def get_queue_type(self, obj: StoryRequest) -> str:
        return obj.queue_type

    def get_characters(self, obj: StoryRequest) -> Any:
        return obj.characters_json

    def get_payment_init_url(self, obj: StoryRequest) -> str | None:
        if obj.plan != StoryRequest.Plan.PAID:
            return None
        if obj.status != StoryRequest.Status.PAYMENT_REQUIRED:
            return None
        request = self.context.get("request")
        url = reverse("billing:payment-init")
        return request.build_absolute_uri(url) if request else url

    def get_child(self, obj: StoryRequest) -> Any:
        if not obj.child:
            return None
        return ChildSummarySerializer(obj.child).data


class RequestTransitionSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = RequestTransition
        fields = ("from_status", "to_status", "note", "actor", "created_at")
        read_only_fields = fields
