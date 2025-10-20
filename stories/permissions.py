from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsOwnerOrStaffForStory(BasePermission):
    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        return getattr(obj, "owner_id", None) == user.id


class IsStaff(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_staff)

    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)
