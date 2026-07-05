import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from university.models import Student

from .models import Attendance, Grade, Lesson
from .permissions import get_assignment_or_403, get_teacher_assignments


def get_ects_and_national(score_percentage):
    if score_percentage >= 90:
        return "A", "Відмінно"
    elif score_percentage >= 82:
        return "B", "Добре"
    elif score_percentage >= 74:
        return "C", "Добре"
    elif score_percentage >= 64:
        return "D", "Задовільно"
    elif score_percentage >= 60:
        return "E", "Задовільно"
    elif score_percentage >= 35:
        return "FX", "Незадовільно (FX)"
    else:
        return "F", "Незадовільно (F)"


@login_required
def dashboard(request):
    """Стартова сторінка: студент бачить власні оцінки, решта — список
    журналів, до яких вони мають дозвіл (для admin/dean — усі журнали)."""
    user = request.user
    if getattr(user, "is_student_role", False):
        return redirect("journal:my_grades")

    assignments = get_teacher_assignments(user).select_related("discipline", "group", "semester", "teacher")
    return render(request, "journal/dashboard.html", {"assignments": assignments})


def _build_grid_context(assignment):
    """Збирає дані для таблиці-журналу (сітки)."""
    all_lessons = list(
        assignment.lessons.order_by("lesson_type", "order_number")
    )

    type_order = [
        (Lesson.Type.LECTURE, "Лекції"),
        (Lesson.Type.PRACTICE, "Практичні"),
        (Lesson.Type.LAB, "Лабораторні"),
    ]
    lessons_by_type = []
    for lt, label in type_order:
        group = [l for l in all_lessons if l.lesson_type == lt]
        if group:
            lessons_by_type.append((label, group))

    students = list(
        Student.objects.filter(group=assignment.group, is_active=True)
        .select_related("user")
        .order_by("user__last_name")
    )

    # Оцінки
    grades_qs = Grade.objects.filter(
        lesson__assignment=assignment,
        grade_type=Grade.GradeType.CURRENT,
    )
    grade_map = {(g.student_id, g.lesson_id): g.value for g in grades_qs}

    # Відсутності
    absent_qs = Attendance.objects.filter(
        lesson__assignment=assignment,
        status=Attendance.Status.ABSENT,
    )
    absent_set = {(a.student_id, a.lesson_id) for a in absent_qs}

    return {
        "lessons_by_type": lessons_by_type,
        "all_lessons": all_lessons,
        "students": students,
        "grade_map": grade_map,
        "absent_set": absent_set,
    }


@login_required
def assignment_detail(request, assignment_id):
    """Журнал-сітка: таблиця «студенти × заняття» з рядком максимальних оцінок.

    Дані зберігаються в реальному часі через AJAX (save_cell).
    """
    assignment = get_assignment_or_403(request.user, assignment_id)
    ctx = _build_grid_context(assignment)

    all_lessons = ctx["all_lessons"]
    students = ctx["students"]
    grade_map = ctx["grade_map"]
    absent_set = ctx["absent_set"]

    if not all_lessons:
        return render(request, "journal/assignment_detail.html", {
            "assignment": assignment,
            "lessons_by_type": [],
            "all_lessons": [],
            "students": students,
            "student_rows": [],
            "no_lessons": True,
        })

    # Побудувати рядки для шаблону
    total_max_grade = sum(l.max_grade for l in all_lessons if l.max_grade is not None)
    student_rows = []
    for student in students:
        cells = []
        total = 0
        for lesson in all_lessons:
            is_absent = (student.id, lesson.id) in absent_set
            grade_val = grade_map.get((student.id, lesson.id))
            if is_absent:
                display = "н"
            elif grade_val is not None:
                display = str(grade_val)
                total += grade_val
            else:
                display = ""
            cells.append({
                "student_id": student.id,
                "lesson_id": lesson.id,
                "display": display,
                "is_absent": is_absent,
            })

        percentage = (total / total_max_grade * 100) if total_max_grade > 0 else 0
        if total_max_grade > 0:
            ects, national = get_ects_and_national(percentage)
        else:
            ects, national = get_ects_and_national(total)

        student_rows.append({
            "student": student,
            "cells": cells,
            "total": total,
            "ects": ects,
            "national": national,
        })

    return render(request, "journal/assignment_detail.html", {
        "assignment": assignment,
        "lessons_by_type": ctx["lessons_by_type"],
        "all_lessons": all_lessons,
        "students": students,
        "student_rows": student_rows,
        "total_max_grade": total_max_grade,
        "no_lessons": False,
    })


@require_POST
@login_required
def save_cell(request, assignment_id):
    """AJAX-ендпоінт для збереження однієї клітинки журналу в реальному часі.

    Очікує JSON: {"lesson_id": int, "student_id": int|null, "value": str}
    - value = число → зберігає Grade, знімає ABSENT
    - value = "н"   → ставить Attendance(ABSENT), видаляє Grade
    - value = ""    → видаляє Grade та ABSENT
    - student_id = null → зберігає max_grade для заняття
    """
    assignment = get_assignment_or_403(request.user, assignment_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    lesson_id = data.get("lesson_id")
    student_id = data.get("student_id")
    value = str(data.get("value", "")).strip()

    # Перевірити, що заняття належить цьому assignment
    try:
        lesson = Lesson.objects.get(pk=lesson_id, assignment=assignment)
    except Lesson.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Lesson not found"}, status=404)

    # --- Збереження max_grade (рядок макс. оцінок) ---
    if student_id is None:
        if value == "" or value.lower() == "none":
            lesson.max_grade = None
        else:
            try:
                lesson.max_grade = int(value)
            except ValueError:
                return JsonResponse({"ok": False, "error": "Invalid max_grade"}, status=400)
        lesson.save(update_fields=["max_grade"])
        return JsonResponse({"ok": True, "saved": lesson.max_grade})

    # --- Збереження оцінки / відсутності студента ---
    # Перевірити, що студент із цієї групи
    try:
        student = Student.objects.get(pk=student_id, group=assignment.group, is_active=True)
    except Student.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Student not found"}, status=404)

    if value.lower() == "н" or value.lower() == "n":
        # Ставимо «відсутній»
        Attendance.objects.update_or_create(
            student=student, lesson=lesson,
            defaults={"status": Attendance.Status.ABSENT},
        )
        # Видаляємо оцінку, якщо була
        Grade.objects.filter(
            student=student, lesson=lesson, grade_type=Grade.GradeType.CURRENT
        ).delete()
        return JsonResponse({"ok": True, "saved": "н", "is_absent": True})

    elif value == "":
        # Очищаємо клітинку
        Grade.objects.filter(
            student=student, lesson=lesson, grade_type=Grade.GradeType.CURRENT
        ).delete()
        Attendance.objects.filter(
            student=student, lesson=lesson, status=Attendance.Status.ABSENT
        ).delete()
        return JsonResponse({"ok": True, "saved": "", "is_absent": False})

    else:
        # Числова оцінка
        try:
            grade_value = int(value)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Введіть число або 'н'"}, status=400)

        if grade_value < 0:
            return JsonResponse({"ok": False, "error": "Оцінка не може бути від'ємною"}, status=400)

        # Перевірка max_grade
        if lesson.max_grade is not None and grade_value > lesson.max_grade:
            return JsonResponse({
                "ok": False,
                "error": f"Оцінка ({grade_value}) перевищує максимум ({lesson.max_grade})"
            }, status=400)

        Grade.objects.update_or_create(
            student=student, lesson=lesson, grade_type=Grade.GradeType.CURRENT,
            defaults={"value": grade_value, "created_by": request.user},
        )
        # Знімаємо «відсутній», якщо був
        Attendance.objects.filter(
            student=student, lesson=lesson, status=Attendance.Status.ABSENT
        ).delete()
        return JsonResponse({"ok": True, "saved": grade_value, "is_absent": False})


@login_required
def gradebook_matrix(request, assignment_id):
    """Зведена таблиця «студенти × заняття» — read-only версія журналу."""
    assignment = get_assignment_or_403(request.user, assignment_id)
    ctx = _build_grid_context(assignment)

    all_lessons = ctx["all_lessons"]
    grade_map = ctx["grade_map"]
    absent_set = ctx["absent_set"]

    total_max_grade = sum(l.max_grade for l in all_lessons if l.max_grade is not None)
    table = []
    for s in ctx["students"]:
        cells = []
        total = 0
        for lesson in all_lessons:
            is_absent = (s.id, lesson.id) in absent_set
            grade_val = grade_map.get((s.id, lesson.id))
            if is_absent:
                cells.append({"display": "н", "is_absent": True})
            elif grade_val is not None:
                cells.append({"display": grade_val, "is_absent": False})
                total += grade_val
            else:
                cells.append({"display": "", "is_absent": False})

        percentage = (total / total_max_grade * 100) if total_max_grade > 0 else 0
        if total_max_grade > 0:
            ects, national = get_ects_and_national(percentage)
        else:
            ects, national = get_ects_and_national(total)

        table.append({
            "student": s,
            "cells": cells,
            "total": total,
            "ects": ects,
            "national": national,
        })

    return render(
        request,
        "journal/gradebook_matrix.html",
        {
            "assignment": assignment,
            "lessons_by_type": ctx["lessons_by_type"],
            "all_lessons": all_lessons,
            "table": table,
            "total_max_grade": total_max_grade,
        },
    )


@login_required
def my_grades(request):
    """Особистий кабінет студента: зведена відомість дисциплін з ECTS рейтингом та відвідуваністю."""
    student = get_object_or_404(Student, user=request.user)

    assignments = TeacherAssignment.objects.filter(
        group=student.group, is_active=True
    ).select_related("discipline", "semester", "teacher")

    discipline_summaries = []

    for assignment in assignments:
        all_lessons = list(assignment.lessons.order_by("lesson_type", "order_number"))
        total_max_grade = sum(l.max_grade for l in all_lessons if l.max_grade is not None)

        # Оцінки за заняття
        grades = Grade.objects.filter(
            student=student, lesson__assignment=assignment, grade_type=Grade.GradeType.CURRENT
        ).select_related("lesson")
        grade_map = {g.lesson_id: g.value for g in grades}

        # Відсутності
        absences = Attendance.objects.filter(
            student=student, lesson__assignment=assignment, status=Attendance.Status.ABSENT
        )
        absences_set = {a.lesson_id for a in absences}

        total_score = sum(grade_map.values())

        percentage = (total_score / total_max_grade * 100) if total_max_grade > 0 else 0
        if total_max_grade > 0:
            ects, national = get_ects_and_national(percentage)
        else:
            ects, national = get_ects_and_national(total_score)

        # Детальна сітка занять для відомості
        lesson_details = []
        for l in all_lessons:
            is_absent = l.id in absences_set
            grade_val = grade_map.get(l.id)
            if is_absent:
                val_display = "н"
            elif grade_val is not None:
                val_display = str(grade_val)
            else:
                val_display = ""

            lesson_details.append({
                "lesson": l,
                "grade": val_display,
                "is_absent": is_absent,
            })

        discipline_summaries.append({
            "assignment": assignment,
            "total_score": total_score,
            "total_max_grade": total_max_grade,
            "ects": ects,
            "national": national,
            "lesson_details": lesson_details,
        })

    return render(
        request,
        "journal/student_grades.html",
        {
            "student": student,
            "discipline_summaries": discipline_summaries,
        }
    )
