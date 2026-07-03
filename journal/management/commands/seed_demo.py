from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from journal.models import TeacherAssignment
from university.models import CurriculumEntry, Discipline, Faculty, Group, Semester, Specialty, Student

User = get_user_model()


class Command(BaseCommand):
    help = "Створює демонстраційні дані для електронного журналу (факультет, групи, дисципліни, викладачів)"

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                "admin", "admin@example.com", "admin12345", role=User.Role.ADMIN,
                first_name="Адмін", last_name="Системи",
            )
            self.stdout.write(self.style.SUCCESS("Створено суперкористувача admin / admin12345"))

        dean, _ = User.objects.get_or_create(
            username="dean",
            defaults=dict(role=User.Role.DEAN, first_name="Ольга", last_name="Деканова", email="dean@example.com"),
        )
        dean.set_password("dean12345")
        dean.save()

        faculty, _ = Faculty.objects.get_or_create(
            code="FIT", defaults={"name": "Факультет інформаційних технологій"}
        )
        specialty, _ = Specialty.objects.get_or_create(
            faculty=faculty, code="121", defaults={"name": "Інженерія програмного забезпечення"}
        )
        group, _ = Group.objects.get_or_create(specialty=specialty, name="ІПЗ-101", defaults={"course": 1})

        discipline_prog, _ = Discipline.objects.get_or_create(
            code="OP-101", defaults={"name": "Основи програмування"}
        )
        discipline_math, _ = Discipline.objects.get_or_create(
            code="MATH-101", defaults={"name": "Вища математика"}
        )

        semester, _ = Semester.objects.get_or_create(
            name="1 семестр", academic_year="2025/2026", defaults={"is_current": True}
        )

        CurriculumEntry.objects.get_or_create(
            specialty=specialty, discipline=discipline_prog, course=1, semester=semester, defaults={"hours": 120}
        )
        CurriculumEntry.objects.get_or_create(
            specialty=specialty, discipline=discipline_math, course=1, semester=semester, defaults={"hours": 90}
        )

        teacher_prog, _ = User.objects.get_or_create(
            username="teacher_prog",
            defaults=dict(role=User.Role.TEACHER, first_name="Іван", last_name="Кодер", email="teacher_prog@example.com"),
        )
        teacher_prog.set_password("teacher12345")
        teacher_prog.save()

        teacher_math, _ = User.objects.get_or_create(
            username="teacher_math",
            defaults=dict(role=User.Role.TEACHER, first_name="Марія", last_name="Числова", email="teacher_math@example.com"),
        )
        teacher_math.set_password("teacher12345")
        teacher_math.save()

        # Ключова демонстрація: дозволи з кількістю пар за семестр.
        # sync_lessons() викликається автоматично при save().
        TeacherAssignment.objects.get_or_create(
            teacher=teacher_prog, discipline=discipline_prog, group=group, semester=semester,
            defaults={"num_lectures": 10, "num_practicals": 5, "num_labs": 8},
        )
        TeacherAssignment.objects.get_or_create(
            teacher=teacher_math, discipline=discipline_math, group=group, semester=semester,
            defaults={"num_lectures": 12, "num_practicals": 8, "num_labs": 0},
        )

        for i in range(1, 6):
            username = f"student{i}"
            student_user, _ = User.objects.get_or_create(
                username=username,
                defaults=dict(role=User.Role.STUDENT, first_name="Студент", last_name=f"№{i}", email=f"{username}@example.com"),
            )
            student_user.set_password("student12345")
            student_user.save()
            Student.objects.get_or_create(
                user=student_user, defaults={"group": group, "record_book_number": f"2025-{i:04d}"}
            )

        self.stdout.write(self.style.SUCCESS("Демо-дані створено успішно!"))
        self.stdout.write(
            "Логіни:\n"
            "  admin / admin12345          — повний доступ\n"
            "  dean / dean12345            — деканат: структура + видача дозволів\n"
            "  teacher_prog / teacher12345 — бачить ЛИШЕ 'Основи програмування' у ІПЗ-101\n"
            "  teacher_math / teacher12345 — бачить ЛИШЕ 'Вищу математику' у ІПЗ-101\n"
            "  student1..student5 / student12345 — власні оцінки"
        )
