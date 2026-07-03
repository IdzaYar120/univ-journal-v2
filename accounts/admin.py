from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "last_name", "first_name", "role", "email", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "last_name", "first_name", "email")
    ordering = ("last_name", "first_name")

    fieldsets = UserAdmin.fieldsets + (
        ("Додатково", {"fields": ("role", "patronymic", "phone")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Додатково", {"fields": ("role", "patronymic", "phone", "email")}),
    )

    def has_module_permission(self, request):
        u = request.user
        return u.is_superuser or getattr(u, "role", None) in ("admin", "dean")

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, "role", None) == "admin"
