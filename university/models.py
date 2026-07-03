from django.conf import settings
from django.db import models


class Faculty(models.Model):
    name = models.CharField("Назва факультету", max_length=255)
    code = models.CharField("Код", max_length=20, unique=True)

    class Meta:
        verbose_name = "Факультет"
        verbose_name_plural = "Факультети"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Specialty(models.Model):
    faculty = models.ForeignKey(
        Faculty, on_delete=models.CASCADE, related_name="specialties", verbose_name="Факультет"
    )
    name = models.CharField("Назва спеціальності", max_length=255)
    code = models.CharField("Код спеціальності", max_length=20)

    class Meta:
        verbose_name = "Спеціальність"
        verbose_name_plural = "Спеціальності"
        unique_together = ("faculty", "code")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class Group(models.Model):
    specialty = models.ForeignKey(
        Specialty, on_delete=models.CASCADE, related_name="groups", verbose_name="Спеціальність"
    )
    name = models.CharField("Назва групи", max_length=50)
    course = models.PositiveSmallIntegerField("Курс", default=1)
    curator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="curated_groups",
        verbose_name="Куратор",
        limit_choices_to={"role__in": ["teacher", "dean", "admin"]},
    )

    class Meta:
        verbose_name = "Група"
        verbose_name_plural = "Групи"
        ordering = ["specialty", "course", "name"]

    def __str__(self):
        return self.name


class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        verbose_name="Облік. запис",
        limit_choices_to={"role": "student"},
    )
    group = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, blank=True, related_name="students", verbose_name="Група"
    )
    record_book_number = models.CharField("№ зачітної книжки", max_length=30, unique=True)
    is_active = models.BooleanField("Навчається", default=True)

    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенти"
        ordering = ["group", "user__last_name"]

    def __str__(self):
        return str(self.user)


class Discipline(models.Model):
    name = models.CharField("Назва дисципліни", max_length=255)
    code = models.CharField("Код дисципліни", max_length=30, unique=True)

    class Meta:
        verbose_name = "Дисципліна"
        verbose_name_plural = "Дисципліни"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Semester(models.Model):
    name = models.CharField("Назва семестру", max_length=100)
    academic_year = models.CharField("Навчальний рік", max_length=20)
    is_current = models.BooleanField("Поточний", default=False)

    class Meta:
        verbose_name = "Семестр"
        verbose_name_plural = "Семестри"
        ordering = ["-academic_year", "name"]

    def __str__(self):
        return f"{self.name} ({self.academic_year})"


class CurriculumEntry(models.Model):
    """Навчальний план: яка дисципліна вивчається якою спеціальністю/курсом у якому семестрі."""

    specialty = models.ForeignKey(
        Specialty, on_delete=models.CASCADE, related_name="curriculum_entries", verbose_name="Спеціальність"
    )
    discipline = models.ForeignKey(
        Discipline, on_delete=models.CASCADE, related_name="curriculum_entries", verbose_name="Дисципліна"
    )
    course = models.PositiveSmallIntegerField("Курс")
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="curriculum_entries", verbose_name="Семестр"
    )
    hours = models.PositiveIntegerField("Кількість годин", default=0)

    class Meta:
        verbose_name = "Пункт навчального плану"
        verbose_name_plural = "Навчальний план"
        unique_together = ("specialty", "discipline", "course", "semester")

    def __str__(self):
        return f"{self.discipline} — {self.specialty} (курс {self.course})"
