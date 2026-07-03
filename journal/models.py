from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from university.models import Discipline, Group, Semester, Student


class TeacherAssignment(models.Model):
    """Головна модель прав доступу до журналу.

    Це і є той самий "дозвіл", який деканат/адміністратор видає викладачу:
    конкретний викладач отримує доступ ЛИШЕ до журналу вказаної дисципліни
    у вказаній групі в конкретному семестрі. Наприклад, викладач "Основ
    програмування" отримує TeacherAssignment(discipline=Основи програмування,
    group=ІПЗ-101) і фізично не бачить журнали інших дисциплін чи груп —
    ані у власному кабінеті, ані в адмінці (див. journal/permissions.py
    та journal/admin.py).

    Поля num_lectures / num_practicals / num_labs задають кількість
    занять за семестр. При збереженні автоматично генерується сітка
    (Lesson-записи), яку викладач бачить у кабінеті як таблицю-журнал.
    """

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Викладач",
        limit_choices_to={"role": "teacher"},
    )
    discipline = models.ForeignKey(
        Discipline, on_delete=models.CASCADE, related_name="assignments", verbose_name="Дисципліна"
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="assignments", verbose_name="Група")
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="assignments", verbose_name="Семестр"
    )
    is_active = models.BooleanField("Активний доступ", default=True)

    num_lectures = models.PositiveSmallIntegerField("Кількість лекцій", default=0)
    num_practicals = models.PositiveSmallIntegerField("Кількість практичних", default=0)
    num_labs = models.PositiveSmallIntegerField("Кількість лабораторних", default=0)

    class Meta:
        verbose_name = "Дозвіл викладачу на журнал"
        verbose_name_plural = "Дозволи викладачам на журнали"
        unique_together = ("teacher", "discipline", "group", "semester")

    def __str__(self):
        return f"{self.teacher} → {self.discipline} / {self.group} / {self.semester}"

    def sync_lessons(self):
        """Синхронізує кількість Lesson-записів із num_lectures / num_practicals / num_labs.

        Додає нові або видаляє зайві (тільки ті, що не мають оцінок).
        Порядок: lesson_type + order_number.
        """
        for lesson_type, desired_count in [
            (Lesson.Type.LECTURE, self.num_lectures),
            (Lesson.Type.PRACTICE, self.num_practicals),
            (Lesson.Type.LAB, self.num_labs),
        ]:
            existing = list(
                self.lessons.filter(lesson_type=lesson_type).order_by("order_number")
            )
            current_count = len(existing)

            if current_count < desired_count:
                # Додати нові заняття
                for i in range(current_count + 1, desired_count + 1):
                    Lesson.objects.create(
                        assignment=self,
                        lesson_type=lesson_type,
                        order_number=i,
                    )
            elif current_count > desired_count:
                # Видалити зайві з кінця (лише ті, де немає оцінок)
                to_remove = existing[desired_count:]
                for lesson in reversed(to_remove):
                    if not lesson.grades.exists() and not lesson.attendance.exists():
                        lesson.delete()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Синхронізуємо сітку при кожному збереженні
        self.sync_lessons()


class Lesson(models.Model):
    class Type(models.TextChoices):
        LECTURE = "lecture", "Лекція"
        PRACTICE = "practice", "Практичне"
        LAB = "lab", "Лабораторне"

    assignment = models.ForeignKey(
        TeacherAssignment, on_delete=models.CASCADE, related_name="lessons", verbose_name="Дозвіл (журнал)"
    )
    order_number = models.PositiveSmallIntegerField("Порядковий номер", default=1)
    topic = models.CharField("Тема", max_length=255, blank=True)
    lesson_type = models.CharField("Тип заняття", max_length=20, choices=Type.choices, default=Type.LECTURE)
    max_grade = models.PositiveSmallIntegerField("Максимальна оцінка", null=True, blank=True)

    class Meta:
        verbose_name = "Заняття"
        verbose_name_plural = "Заняття"
        ordering = ["lesson_type", "order_number"]
        unique_together = ("assignment", "lesson_type", "order_number")

    def __str__(self):
        return f"{self.get_lesson_type_display()} №{self.order_number} — {self.assignment.discipline}"


class Grade(models.Model):
    class GradeType(models.TextChoices):
        CURRENT = "current", "Поточна"
        MODULE = "module", "Модульна"
        EXAM = "exam", "Екзамен/Залік"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="grades", verbose_name="Студент")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="grades", verbose_name="Заняття")
    value = models.PositiveSmallIntegerField("Оцінка")
    grade_type = models.CharField(
        "Тип оцінки", max_length=20, choices=GradeType.choices, default=GradeType.CURRENT
    )
    comment = models.CharField("Коментар", max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="grades_given",
        verbose_name="Виставив",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Оцінка"
        verbose_name_plural = "Оцінки"
        unique_together = ("student", "lesson", "grade_type")

    def clean(self):
        if self.value is not None and self.lesson_id:
            max_g = self.lesson.max_grade
            if max_g is not None and self.value > max_g:
                raise ValidationError(
                    f"Оцінка ({self.value}) не може перевищувати максимум ({max_g}) для цього заняття."
                )
        if self.student_id and self.lesson_id and self.student.group_id != self.lesson.assignment.group_id:
            raise ValidationError("Студент не належить до групи цього заняття")

    def __str__(self):
        return f"{self.student} — {self.value}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Присутній"
        ABSENT = "absent", "Відсутній"
        LATE = "late", "Запізнення"
        EXCUSED = "excused", "Відсутній (поважна причина)"

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance", verbose_name="Студент"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="attendance", verbose_name="Заняття"
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.PRESENT)

    class Meta:
        verbose_name = "Відвідуваність"
        verbose_name_plural = "Відвідуваність"
        unique_together = ("student", "lesson")

    def __str__(self):
        return f"{self.student} — {self.get_status_display()}"
