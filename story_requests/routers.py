from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StoryRequestViewSet

router = DefaultRouter()
router.register("requests", StoryRequestViewSet, basename="story-request")

urlpatterns = [
    path("", include(router.urls)),
]
