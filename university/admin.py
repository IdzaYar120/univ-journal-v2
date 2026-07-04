from django.contrib import admin

from journal.models import TeacherAssignment
from .models import CurriculumEntry, Discipline, Faculty, Group, Semester, Specialty, Student


class StructureManagedAdmin(admin.ModelAdmin):
    """Базовий клас: цю частину журналу веде лише деканат/адміністратор.

    Викладачі взагалі не бачать ці розділи в адмінці — вони отримують доступ
    лише до конкретних журналів через TeacherAssignment (див. журнал -> journal.admin).
    """

    def _is_dean_or_admin(self, user):
        return user.is_authenticated and (user.is_superuser or getattr(user, "role", None) in ("admin", "dean"))

    def has_module_permission(self, request):
        return self._is_dean_or_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return self._is_dean_or_admin(request.user)

    def has_add_permission(self, request):
        return self._is_dean_or_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return self._is_dean_or_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser or getattr(request.user, "role", None) == "admin"


@admin.register(Faculty)
class FacultyAdmin(StructureManagedAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Specialty)
class SpecialtyAdmin(StructureManagedAdmin):
    list_display = ("code", "name", "faculty")
    list_filter = ("faculty",)
    search_fields = ("name", "code")
    autocomplete_fields = ("faculty",)


class StudentInline(admin.TabularInline):
    model = Student
    extra = 0
    autocomplete_fields = ("user",)


class TeacherAssignmentInline(admin.TabularInline):
    model = TeacherAssignment
    extra = 0
    autocomplete_fields = ("teacher", "discipline", "semester")
    verbose_name = "Дисципліна групи (призначення викладача та пар)"
    verbose_name_plural = "Дисципліни групи (призначення викладачів та обсяг пар)"


@admin.register(Group)
class GroupAdmin(StructureManagedAdmin):
    list_display = ("name", "specialty", "course", "curator")
    list_filter = ("specialty__faculty", "specialty", "course")
    search_fields = ("name",)
    autocomplete_fields = ("specialty", "curator")
    inlines = [StudentInline, TeacherAssignmentInline]


@admin.register(Student)
class StudentAdmin(StructureManagedAdmin):
    list_display = ("user", "group", "record_book_number", "is_active")
    list_filter = ("group__specialty", "group", "is_active")
    search_fields = ("user__last_name", "user__first_name", "record_book_number")
    autocomplete_fields = ("user", "group")
    list_editable = ("is_active",)


@admin.register(Discipline)
class DisciplineAdmin(StructureManagedAdmin):
    list_display = ("code", "name")
    search_fields = ("name", "code")


@admin.register(Semester)
class SemesterAdmin(StructureManagedAdmin):
    list_display = ("name", "academic_year", "is_current")
    list_editable = ("is_current",)
    search_fields = ("name", "academic_year")


@admin.register(CurriculumEntry)
class CurriculumEntryAdmin(StructureManagedAdmin):
    list_display = ("specialty", "discipline", "course", "semester", "hours")
    list_filter = ("specialty", "discipline", "semester")
    autocomplete_fields = ("specialty", "discipline", "semester")
