from django.contrib import admin

from .models import CurriculumEntry, Discipline, Faculty, Group, Semester, Specialty, Student


class StructureManagedAdmin(admin.ModelAdmin):
    """Базовий клас: цю частину журналу веде лише деканат/адміністратор.

    Викладачі взагалі не бачать ці розділи в адмінці — вони отримують доступ
    лише до конкретних журналів через TeacherAssignment (див. журнал -> journal.admin).
    """

    def has_module_permission(self, request):
        u = request.user
        return u.is_authenticated and (u.is_superuser or getattr(u, "role", None) in ("admin", "dean"))

    has_view_permission = has_module_permission
    has_add_permission = has_module_permission
    has_change_permission = has_module_permission

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


@admin.register(Group)
class GroupAdmin(StructureManagedAdmin):
    list_display = ("name", "specialty", "course", "curator")
    list_filter = ("specialty__faculty", "specialty", "course")
    search_fields = ("name",)
    autocomplete_fields = ("specialty", "curator")
    inlines = [StudentInline]


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
