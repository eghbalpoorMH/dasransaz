from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view

from .models import StoryRequest
from .permissions import IsOwnerOrStaff
from .serializers import (
    RequestTransitionSerializer,
    StoryRequestCreateSerializer,
    StoryRequestDetailSerializer,
    StoryRequestListSerializer,
)
from .services import calc_position


@extend_schema_view(
    list=extend_schema(
        summary="لیست درخواست‌های کاربر",
        parameters=[],
    ),
    retrieve=extend_schema(summary="جزییات درخواست"),
    create=extend_schema(
        summary="ثبت درخواست تازه برای داستان",
        examples=[
            OpenApiExample(
                "Create free request",
                value={
                    "lang": "fa",
                    "reading_level": "k1",
                    "theme": "ماجراجویی در حمام ایمن",
                    "prompt_note": "قصه مهربان و بامزه باشه",
                    "plan": "free",
                    "characters": [
                        {"name": "علی", "role": "hero", "age": 6, "traits": ["کنجکاو", "مهربان"]},
                        {"name": "سینا", "role": "sidekick", "age": 2, "traits": ["بامزه"]},
                    ],
                },
            )
        ],
    ),
)
class StoryRequestViewSet(viewsets.ModelViewSet):
    """Story request CRUD for end users (create + list + retrieve)."""

    serializer_class = StoryRequestDetailSerializer
    permission_classes = [IsOwnerOrStaff]
    lookup_field = "uuid"

    def get_queryset(self):
        qs = StoryRequest.objects.select_related("user", "child", "payment")
        user = self.request.user
        if not user.is_staff:
            return qs.filter(user=user)

        if self.request.query_params.get("mine"):
            return qs.filter(user=user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return StoryRequestCreateSerializer
        if self.action == "list":
            return StoryRequestListSerializer
        if self.action == "transitions":
            return RequestTransitionSerializer
        return StoryRequestDetailSerializer

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        story_request = serializer.save()
        detail_serializer = StoryRequestDetailSerializer(
            story_request,
            context=self.get_serializer_context(),
        )
        detail_data = detail_serializer.data
        payload = {
            "id": detail_data["id"],
            "status": detail_data["status"],
            "queue_type": detail_data["queue_type"],
            "position": detail_data["position"],
        }
        headers = self.get_success_headers(detail_data)
        return Response(payload, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return response

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        position = calc_position(instance)
        if instance.position_hint != position:
            StoryRequest.objects.filter(pk=instance.pk).update(position_hint=position)
            instance.position_hint = position
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(summary="لیست تاریخچه وضعیت درخواست")
    @action(detail=True, methods=["get"])
    def transitions(self, request, *args, **kwargs):
        story_request = self.get_object()
        serializer = RequestTransitionSerializer(story_request.transitions.all(), many=True)
        return Response(serializer.data)
