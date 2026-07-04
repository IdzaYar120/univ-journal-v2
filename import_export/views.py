from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from journal.models import TeacherAssignment
from journal.permissions import get_teacher_assignments

from .importers import GradebookImporter, StudentImporter, StructureImporter


def _is_admin_or_dean(user):
    return user.is_superuser or getattr(user, "role", None) in ("admin", "dean")


@login_required
def import_hub(request):
    """Головна сторінка імпорту — вибір типу."""
    if not _is_admin_or_dean(request.user):
        messages.error(request, "Доступ лише для деканату та адміністраторів.")
        return redirect("journal:dashboard")

    # Список журналів для імпорту оцінок
    assignments = TeacherAssignment.objects.select_related(
        "teacher", "discipline", "group", "semester"
    ).order_by("discipline__name", "group__name")

    return render(request, "import_export/import_hub.html", {"assignments": assignments})


@login_required
def import_students(request):
    """Імпорт списку студентів."""
    if not _is_admin_or_dean(request.user):
        messages.error(request, "Доступ заборонено.")
        return redirect("journal:dashboard")

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Завантажте файл.")
            return redirect("import_export:import_students")

        try:
            importer = StudentImporter(uploaded_file)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("import_export:import_students")

        if importer.errors:
            return render(request, "import_export/import_preview.html", {
                "import_type": "students",
                "errors": importer.errors,
                "preview_rows": [],
            })

        # Якщо натиснуто «Підтвердити»
        if request.POST.get("confirm") == "1":
            results = importer.execute()
            return render(request, "import_export/import_result.html", {
                "import_type": "students",
                "results": results,
                "preview_rows": importer.preview_rows,
            })

        # Показати превʼю
        return render(request, "import_export/import_preview.html", {
            "import_type": "students",
            "preview_rows": importer.preview_rows,
            "errors": importer.errors,
            "file_name": uploaded_file.name,
        })

    return render(request, "import_export/import_form.html", {
        "import_type": "students",
        "title": "Імпорт списку студентів",
        "description": "Завантажте CSV або Excel файл зі стовпцями: Прізвище, Імʼя, По батькові, Група, № зачітної книжки",
    })


@login_required
def import_structure(request):
    """Імпорт структури або дисциплін."""
    if not _is_admin_or_dean(request.user):
        messages.error(request, "Доступ заборонено.")
        return redirect("journal:dashboard")

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "Завантажте файл.")
            return redirect("import_export:import_structure")

        try:
            importer = StructureImporter(uploaded_file)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("import_export:import_structure")

        if importer.errors:
            return render(request, "import_export/import_preview.html", {
                "import_type": "structure",
                "errors": importer.errors,
                "preview_rows": [],
            })

        if request.POST.get("confirm") == "1":
            results = importer.execute()
            return render(request, "import_export/import_result.html", {
                "import_type": "structure",
                "results": results,
                "sub_type": importer.import_type,
            })

        return render(request, "import_export/import_preview.html", {
            "import_type": "structure",
            "sub_type": importer.import_type,
            "preview_rows": importer.preview_rows,
            "errors": importer.errors,
            "file_name": uploaded_file.name,
        })

    return render(request, "import_export/import_form.html", {
        "import_type": "structure",
        "title": "Імпорт структури / дисциплін",
        "description": "Завантажте CSV/Excel. Для структури: Факультет, Код факультету, Спеціальність, Код спеціальності, Група, Курс. Для дисциплін: Назва дисципліни, Код дисципліни.",
    })


@login_required
def import_gradebook(request):
    """Імпорт журналу оцінок у конкретний TeacherAssignment."""
    user = request.user
    if not (_is_admin_or_dean(user) or getattr(user, "role", None) == "teacher"):
        messages.error(request, "Доступ заборонено.")
        return redirect("journal:dashboard")

    # Доступні журнали
    if _is_admin_or_dean(user):
        assignments = TeacherAssignment.objects.all()
    else:
        assignments = get_teacher_assignments(user)
    assignments = assignments.select_related("teacher", "discipline", "group", "semester")

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")
        assignment_id = request.POST.get("assignment_id")

        if not uploaded_file or not assignment_id:
            messages.error(request, "Виберіть журнал та завантажте файл.")
            return redirect("import_export:import_gradebook")

        try:
            importer = GradebookImporter(uploaded_file, assignment_id=int(assignment_id))
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("import_export:import_gradebook")

        if importer.errors:
            return render(request, "import_export/import_preview.html", {
                "import_type": "gradebook",
                "errors": importer.errors,
                "preview_rows": [],
                "assignments": assignments,
            })

        if request.POST.get("confirm") == "1":
            results = importer.execute()
            return render(request, "import_export/import_result.html", {
                "import_type": "gradebook",
                "results": results,
            })

        return render(request, "import_export/import_preview.html", {
            "import_type": "gradebook",
            "preview_rows": importer.preview_rows,
            "column_lessons": importer.column_lessons,
            "max_grades": importer.max_grades,
            "errors": importer.errors,
            "file_name": uploaded_file.name,
            "assignment_id": assignment_id,
        })

    return render(request, "import_export/import_form.html", {
        "import_type": "gradebook",
        "title": "Імпорт журналу оцінок",
        "description": "Завантажте CSV/Excel з сіткою оцінок. Перший рядок — заголовки (Лекція 1, Лаб 2...), другий — макс. оцінки, далі — студенти.",
        "assignments": assignments,
    })
