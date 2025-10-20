from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsOwnerOrStaff(BasePermission):
    """Allow access to staff or the owner of the story request."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return getattr(obj, "user_id", None) == request.user.id

