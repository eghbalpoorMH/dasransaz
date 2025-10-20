from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_staff)
