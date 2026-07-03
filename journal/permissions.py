"""
Централізована логіка контролю доступу.

Уся система дозволів будується навколо однієї ідеї: доступ викладача
до журналу визначається виключно записами TeacherAssignment, які
може створювати лише деканат/адміністратор (university.admin /
journal.admin забороняють викладачам самим призначати собі дозволи).

Кожен view і кожен ModelAdmin в journal/admin.py фільтрує дані через
get_teacher_assignments(), тож викладач фізично не може отримати
queryset, що виходить за межі своїх призначень — навіть підмінивши
ID в URL (get_object_or_404 працює по вже відфільтрованому queryset).
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import TeacherAssignment


def get_teacher_assignments(user):
    """Повертає queryset дозволених призначень для користувача.

    admin/dean (та суперкористувач) бачать усі призначення (їм потрібно
    керувати ними), викладач — лише свої активні призначення, студент —
    жодного (студенти взаємодіють з журналом через окремий read-only view).
    """
    if not user.is_authenticated:
        return TeacherAssignment.objects.none()
    if user.is_superuser or getattr(user, "role", None) in ("admin", "dean"):
        return TeacherAssignment.objects.filter(is_active=True)
    if getattr(user, "role", None) == "teacher":
        return TeacherAssignment.objects.filter(teacher=user, is_active=True)
    return TeacherAssignment.objects.none()


def get_assignment_or_403(user, assignment_id):
    """Дістає TeacherAssignment, гарантуючи, що він належить дозволам користувача."""
    qs = get_teacher_assignments(user).select_related("discipline", "group", "semester", "teacher")
    return get_object_or_404(qs, pk=assignment_id)


class TeacherAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Пускає у викладацьку частину лише admin/dean/teacher (не студентів)."""

    def test_func(self):
        u = self.request.user
        return bool(
            u.is_authenticated
            and (u.is_superuser or getattr(u, "role", None) in ("admin", "dean", "teacher"))
        )

    def handle_no_permission(self):
        raise PermissionDenied("Немає доступу до журналу.")
