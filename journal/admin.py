from django.contrib import admin

from .models import Attendance, Grade, Lesson, TeacherAssignment


class RoleRestrictedAdmin(admin.ModelAdmin):
    """Базовий клас ізоляції даних: admin/dean бачать усе, викладач — лише
    те, що стосується ЙОГО TeacherAssignment (поле teacher_field_path
    вказує шлях до викладача від поточної моделі)."""

    teacher_field_path = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        u = request.user
        if u.is_superuser or getattr(u, "role", None) in ("admin", "dean"):
            return qs
        if getattr(u, "role", None) == "teacher" and self.teacher_field_path:
            return qs.filter(**{self.teacher_field_path: u})
        return qs.none()

    def has_module_permission(self, request):
        return request.user.is_authenticated and getattr(request.user, "role", None) in (
            "admin",
            "dean",
            "teacher",
        ) or request.user.is_superuser


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(RoleRestrictedAdmin):
    """Видача дозволів. Створювати/змінювати/видаляти дозволи можуть
    лише деканат та адміністратор — викладач бачить свої призначення
    тільки для перегляду і не може сам собі щось додати."""

    teacher_field_path = "teacher"
    list_display = (
        "teacher", "discipline", "group", "semester",
        "num_lectures", "num_practicals", "num_labs", "is_active",
    )
    list_filter = ("discipline", "group", "semester", "is_active")
    autocomplete_fields = ("teacher", "discipline", "group", "semester")
    search_fields = ("teacher__last_name", "teacher__first_name", "discipline__name", "group__name")

    def _is_dean_or_admin(self, request):
        return request.user.is_superuser or getattr(request.user, "role", None) in ("admin", "dean")

    def has_add_permission(self, request):
        return self._is_dean_or_admin(request)

    def has_change_permission(self, request, obj=None):
        return self._is_dean_or_admin(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_dean_or_admin(request)


@admin.register(Lesson)
class LessonAdmin(RoleRestrictedAdmin):
    """Заняття генеруються автоматично при збереженні TeacherAssignment.
    Тут можна лише переглядати / редагувати тему та max_grade."""

    teacher_field_path = "assignment__teacher"
    list_display = ("assignment", "lesson_type", "order_number", "topic", "max_grade")
    list_filter = ("assignment__discipline", "assignment__group", "lesson_type")
    search_fields = ("topic", "assignment__discipline__name", "assignment__group__name")
    readonly_fields = ("assignment", "lesson_type", "order_number")

    def has_add_permission(self, request):
        return False  # Заняття генеруються автоматично

    def has_delete_permission(self, request, obj=None):
        return False  # Видаляються через зміну кількості в TeacherAssignment


@admin.register(Grade)
class GradeAdmin(RoleRestrictedAdmin):
    teacher_field_path = "lesson__assignment__teacher"
    list_display = ("student", "lesson", "value", "grade_type", "created_by")
    list_filter = ("grade_type", "lesson__assignment__discipline")
    autocomplete_fields = ("student", "lesson")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Attendance)
class AttendanceAdmin(RoleRestrictedAdmin):
    teacher_field_path = "lesson__assignment__teacher"
    list_display = ("student", "lesson", "status")
    list_filter = ("status", "lesson__assignment__discipline")
    autocomplete_fields = ("student", "lesson")
