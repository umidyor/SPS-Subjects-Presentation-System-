# spsapp/permissions.py
from rest_framework.permissions import BasePermission


class IsTeacher(BasePermission):
    """O'qituvchilar yoki Adminlar uchun ruxsat"""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_staff or getattr(request.user, 'role', None) == 'teacher')
        )

class IsOwner(BasePermission):
    """Only object owner can access"""
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'teacher'):
            return obj.teacher == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False
