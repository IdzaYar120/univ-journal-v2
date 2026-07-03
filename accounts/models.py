from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Кастомний користувач із роллю в системі.

    Роль визначає, який інтерфейс і які права доступу отримує людина:
    - admin   — повний доступ (IT-адміністратор системи)
    - dean    — деканат/методист: керує студентами, групами, дисциплінами
                та видає викладачам дозволи (TeacherAssignment)
    - teacher — викладач: бачить і редагує ЛИШЕ ті журнали (дисципліна+група),
                на які деканат видав йому дозвіл
    - student — студент: бачить лише власні оцінки та відвідуваність
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Адміністратор"
        DEAN = "dean", "Деканат / Методист"
        TEACHER = "teacher", "Викладач"
        STUDENT = "student", "Студент"

    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.STUDENT)
    patronymic = models.CharField("По батькові", max_length=150, blank=True)
    phone = models.CharField("Телефон", max_length=30, blank=True)

    class Meta:
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self):
        full = f"{self.last_name} {self.first_name} {self.patronymic}".strip()
        return full or self.username

    @property
    def is_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_dean(self):
        return self.role == self.Role.DEAN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student_role(self):
        return self.role == self.Role.STUDENT

    @property
    def can_manage_structure(self):
        """Хто може керувати студентами/групами/дисциплінами та видавати дозволи."""
        return self.is_admin or self.is_dean
