from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PublicStoryDetailView,
    PublicStoryListView,
    StoryFromRequestView,
    StoryScenesBulkView,
    StoryViewSet,
)

app_name = "stories"

router = DefaultRouter()
router.register("stories", StoryViewSet, basename="story")

urlpatterns = [
    path("stories/from-request/<str:request_id>/", StoryFromRequestView.as_view(), name="story-from-request"),
    path("stories/<int:story_id>/scenes/", StoryScenesBulkView.as_view(), name="story-scenes-bulk"),
    path("stories/public/", PublicStoryListView.as_view(), name="public-story-list"),
    path("stories/public/<slug:slug>/", PublicStoryDetailView.as_view(), name="public-story-detail"),
    path("", include(router.urls)),
]
