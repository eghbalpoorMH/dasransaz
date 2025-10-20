from __future__ import annotations

from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db import models
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema

from story_requests.models import StoryRequest

from stories import services
from stories.models import Story
from stories.permissions import IsOwnerOrStaffForStory, IsStaff

from .serializers import (
    PublicStoryDetailSerializer,
    PublicStoryListSerializer,
    StoryDetailSerializer,
    StoryFromRequestSerializer,
    StoryListSerializer,
    StoryScenesBulkSerializer,
)


class StoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Story.objects.select_related("owner", "child", "request").prefetch_related("scenes")
    serializer_class = StoryListSerializer
    permission_classes = [IsAuthenticated]

    permission_classes_by_action = {
        "publish": [IsAuthenticated, IsOwnerOrStaffForStory],
        "unpublish": [IsAuthenticated, IsOwnerOrStaffForStory],
    }

    def get_permissions(self):
        if hasattr(self, "action") and self.action in self.permission_classes_by_action:
            classes = self.permission_classes_by_action[self.action]
            return [permission() for permission in classes]
        return super().get_permissions()

    def get_queryset(self):
        qs = super().get_queryset()
        request = self.request
        user = request.user
        filters = {}
        lang = request.query_params.get("lang")
        if lang:
            filters["lang"] = lang
        level = request.query_params.get("reading_level")
        if level:
            filters["reading_level"] = level

        if user.is_staff:
            if filters:
                qs = qs.filter(**filters)
            return qs

        qs = qs.filter(owner=user, is_hidden=False, status__in=[Story.Status.READY, Story.Status.PUBLISHED])
        if filters:
            qs = qs.filter(**filters)
        return qs

    def get_serializer_class(self):
        if self.action in {"retrieve", "publish", "unpublish"}:
            return StoryDetailSerializer
        return StoryListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action in {"retrieve", "publish", "unpublish"}:
            include = self.request.query_params.get("include") == "scenes"
            context["include_scenes"] = include
        return context

    @extend_schema(
        parameters=[
            OpenApiParameter(name="mine", location=OpenApiParameter.QUERY, description="برای مشاهده داستان‌های من مقدار ۱"),
            OpenApiParameter(name="lang", location=OpenApiParameter.QUERY, required=False, description="فیلتر زبان"),
            OpenApiParameter(name="reading_level", location=OpenApiParameter.QUERY, required=False, description="فیلتر سطح مطالعه"),
        ],
        responses=StoryListSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        if not request.user.is_staff and request.query_params.get("mine") != "1":
            raise Http404
        return super().list(request, *args, **kwargs)

    @extend_schema(
        parameters=[OpenApiParameter(name="include", location=OpenApiParameter.QUERY, description="برای اضافه‌کردن scenes مقدار scenes بفرستید")],
        responses=StoryDetailSerializer,
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def get_object(self):
        story = super().get_object()
        user = self.request.user
        if user.is_staff:
            return story
        if story.owner_id != user.id:
            raise Http404
        if story.is_hidden or story.status == Story.Status.DRAFT:
            raise Http404
        return story

    @extend_schema(
        request=None,
        responses={
            200: StoryDetailSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    )
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        story = self.get_object()
        try:
            services.publish_story(story, actor=request.user)
        except ValidationError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        serializer = StoryDetailSerializer(story, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(request=None, responses=StoryDetailSerializer)
    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        story = self.get_object()
        try:
            services.unpublish_story(story, actor=request.user)
        except ValidationError as exc:
            return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)
        serializer = StoryDetailSerializer(story, context=self.get_serializer_context())
        return Response(serializer.data)


class StoryFromRequestView(APIView):
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(request=StoryFromRequestSerializer, responses=StoryDetailSerializer)
    def post(self, request, request_id: str):
        serializer = StoryFromRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        story_request = self._resolve_request(request_id)
        story = services.create_story_from_request(
            story_request,
            title=serializer.validated_data["title"],
            scenes_data=serializer.validated_data.get("scenes", []),
        )
        story_serializer = StoryDetailSerializer(story, context={"request": request, "include_scenes": True})
        return Response(story_serializer.data, status=status.HTTP_201_CREATED)

    def _resolve_request(self, identifier: str) -> StoryRequest:
        queryset = StoryRequest.objects.all()
        try:
            return queryset.get(pk=int(identifier))
        except (ValueError, StoryRequest.DoesNotExist):
            pass

        if identifier.startswith("req_"):
            token = identifier.split("_", 1)[1]
            return get_object_or_404(queryset, uuid__istartswith=token)

        return get_object_or_404(queryset, uuid=identifier)


class StoryScenesBulkView(APIView):
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(request=StoryScenesBulkSerializer, responses=StoryDetailSerializer)
    def put(self, request, story_id: int):
        payload = StoryScenesBulkSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        story = get_object_or_404(Story, pk=story_id)
        services.upsert_scenes(story, payload.validated_data["scenes"])
        story.refresh_from_db()
        story_serializer = StoryDetailSerializer(story, context={"request": request, "include_scenes": True})
        return Response(story_serializer.data)


class DefaultStoryPagination(PageNumberPagination):
    page_size = 20


class PublicStoryListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicStoryListSerializer
    pagination_class = DefaultStoryPagination

    @extend_schema(
        parameters=[
            OpenApiParameter(name="lang", location=OpenApiParameter.QUERY, required=False, description="فیلتر زبان"),
            OpenApiParameter(name="reading_level", location=OpenApiParameter.QUERY, required=False, description="سطح مطالعه"),
            OpenApiParameter(name="q", location=OpenApiParameter.QUERY, required=False, description="جستجو در عنوان یا خلاصه"),
        ],
        responses=PublicStoryListSerializer(many=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Story.objects.filter(
            status=Story.Status.PUBLISHED,
            visibility=Story.Visibility.PUBLIC,
            is_hidden=False,
        ).order_by("-published_at")
        lang = self.request.query_params.get("lang")
        if lang:
            queryset = queryset.filter(lang=lang)
        level = self.request.query_params.get("reading_level")
        if level:
            queryset = queryset.filter(reading_level=level)
        query = self.request.query_params.get("q")
        if query:
            queryset = queryset.filter(models.Q(title__icontains=query) | models.Q(summary__icontains=query))
        return queryset


class PublicStoryDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter(name="include", location=OpenApiParameter.QUERY, required=False, description="scenes برای دریافت صفحات")],
        responses=PublicStoryDetailSerializer,
    )
    def get(self, request, slug: str):
        story = get_object_or_404(
            Story,
            slug=slug,
            status=Story.Status.PUBLISHED,
            visibility=Story.Visibility.PUBLIC,
            is_hidden=False,
        )
        include = request.query_params.get("include") == "scenes"
        serializer = PublicStoryDetailSerializer(
            story,
            context={"request": request, "include_scenes": include},
        )
        return Response(serializer.data)
