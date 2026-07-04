"""Парсери для імпорту CSV/Excel файлів.

Три типи імпорту:
1. StudentImporter — список студентів (прізвище, імʼя, група, залікова)
2. StructureImporter — факультети, спеціальності, групи, дисципліни
3. GradebookImporter — журнал оцінок (сітка студенти × заняття)
"""

import csv
import io
import re
import secrets
import string

import openpyxl
from django.contrib.auth import get_user_model

from journal.models import Attendance, Grade, Lesson, TeacherAssignment
from university.models import Discipline, Faculty, Group, Semester, Specialty, Student

User = get_user_model()


def _read_file(uploaded_file):
    """Читає завантажений файл (CSV або Excel) і повертає список рядків (list of dicts або list of lists)."""
    name = uploaded_file.name.lower()

    if name.endswith(".xlsx"):
        wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append([str(cell).strip() if cell is not None else "" for cell in row])
        wb.close()
        return rows

    elif name.endswith(".csv"):
        content = uploaded_file.read()
        # Спроба декодувати як utf-8, потім cp1251 (Windows-1251 часто в укр. файлах)
        for encoding in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Не вдалося декодувати файл. Спробуйте UTF-8 або Windows-1251.")

        reader = csv.reader(io.StringIO(text))
        return [row for row in reader]

    else:
        raise ValueError("Підтримуються лише .csv та .xlsx файли.")


def _transliterate(text):
    """Проста транслітерація українського тексту для генерації username."""
    table = {
        "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d",
        "е": "e", "є": "ye", "ж": "zh", "з": "z", "и": "y", "і": "i",
        "ї": "yi", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
        "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ь": "", "ю": "yu", "я": "ya", "'": "", "ʼ": "",
    }
    result = []
    for ch in text.lower():
        result.append(table.get(ch, ch))
    # Залишити лише a-z, 0-9, _, -
    return re.sub(r"[^a-z0-9_-]", "", "".join(result))


def _gen_password(length=8):
    """Генерує випадковий пароль."""
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


# ═══════════════════════════════════════════════════════════════════
# 1. ІМПОРТ СТУДЕНТІВ
# ═══════════════════════════════════════════════════════════════════

class StudentImporter:
    """
    Очікуваний формат (перший рядок — заголовки):
    Прізвище | Імʼя | По батькові | Група | № зачітної книжки
    """

    REQUIRED_HEADERS = {"прізвище", "ім'я", "група", "№ зачітної книжки"}
    HEADER_ALIASES = {
        "прізвище": "last_name",
        "прiзвище": "last_name",
        "імʼя": "first_name",
        "ім'я": "first_name",
        "имя": "first_name",
        "по батькові": "patronymic",
        "група": "group",
        "№ зачітної книжки": "record_book",
        "номер залікової": "record_book",
        "залікова": "record_book",
        "зачітна": "record_book",
        "record_book": "record_book",
    }

    def __init__(self, uploaded_file):
        self.rows_raw = _read_file(uploaded_file)
        self.errors = []
        self.preview_rows = []
        self.results = {"created": 0, "skipped": 0, "errors": []}
        self._parse()

    def _parse(self):
        if len(self.rows_raw) < 2:
            self.errors.append("Файл порожній або містить лише заголовки.")
            return

        # Розпізнати заголовки
        raw_headers = [h.strip().lower() for h in self.rows_raw[0]]
        self.col_map = {}
        for i, h in enumerate(raw_headers):
            for alias, field in self.HEADER_ALIASES.items():
                if alias in h:
                    self.col_map[field] = i
                    break

        missing = set()
        for req in ("last_name", "first_name", "group", "record_book"):
            if req not in self.col_map:
                missing.add(req)
        if missing:
            self.errors.append(f"Не знайдено стовпці: {', '.join(missing)}. Заголовки у файлі: {raw_headers}")
            return

        # Парсити рядки
        for row_idx, row in enumerate(self.rows_raw[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue  # Пропустити порожні рядки
            try:
                last_name = row[self.col_map["last_name"]].strip()
                first_name = row[self.col_map["first_name"]].strip()
                patronymic = row[self.col_map.get("patronymic", -1)].strip() if "patronymic" in self.col_map else ""
                group_name = row[self.col_map["group"]].strip()
                record_book = row[self.col_map["record_book"]].strip()

                if not last_name or not first_name or not record_book:
                    self.errors.append(f"Рядок {row_idx}: пропущено обовʼязкові поля.")
                    continue

                self.preview_rows.append({
                    "last_name": last_name,
                    "first_name": first_name,
                    "patronymic": patronymic,
                    "group_name": group_name,
                    "record_book": record_book,
                })
            except (IndexError, KeyError):
                self.errors.append(f"Рядок {row_idx}: невірний формат.")

    def execute(self):
        """Виконує імпорт: створює User + Student."""
        for row in self.preview_rows:
            record_book = row["record_book"]
            if Student.objects.filter(record_book_number=record_book).exists():
                self.results["skipped"] += 1
                continue

            group = Group.objects.filter(name=row["group_name"]).first()
            if not group:
                self.results["errors"].append(
                    f"Група «{row['group_name']}» не знайдена для {row['last_name']} {row['first_name']}."
                )
                continue

            # Генерація username
            base_username = _transliterate(row["last_name"]) + "_" + _transliterate(row["first_name"][:1])
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            password = _gen_password()

            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=row["first_name"],
                last_name=row["last_name"],
                role="student",
            )
            if row["patronymic"]:
                user.patronymic = row["patronymic"]
                user.save(update_fields=["patronymic"])

            Student.objects.create(
                user=user,
                group=group,
                record_book_number=record_book,
            )

            row["username"] = username
            row["password"] = password
            self.results["created"] += 1

        return self.results


# ═══════════════════════════════════════════════════════════════════
# 2. ІМПОРТ СТРУКТУРИ
# ═══════════════════════════════════════════════════════════════════

class StructureImporter:
    """
    Очікуваний формат (перший рядок — заголовки):
    Факультет | Код факультету | Спеціальність | Код спеціальності | Група | Курс
    АБО для дисциплін:
    Назва дисципліни | Код дисципліни
    """

    def __init__(self, uploaded_file):
        self.rows_raw = _read_file(uploaded_file)
        self.errors = []
        self.preview_rows = []
        self.import_type = None  # "structure" або "disciplines"
        self.results = {"created": 0, "skipped": 0, "errors": []}
        self._parse()

    def _parse(self):
        if len(self.rows_raw) < 2:
            self.errors.append("Файл порожній або містить лише заголовки.")
            return

        raw_headers = [h.strip().lower() for h in self.rows_raw[0]]
        headers_text = " ".join(raw_headers)

        # Визначити тип: структура чи дисципліни
        if "дисциплін" in headers_text or "discipline" in headers_text:
            self.import_type = "disciplines"
            self._parse_disciplines(raw_headers)
        else:
            self.import_type = "structure"
            self._parse_structure(raw_headers)

    def _parse_structure(self, raw_headers):
        col = {}
        for i, h in enumerate(raw_headers):
            if "факультет" in h and "код" not in h:
                col["faculty_name"] = i
            elif "код" in h and "факультет" in h:
                col["faculty_code"] = i
            elif "спеціальність" in h and "код" not in h:
                col["specialty_name"] = i
            elif "код" in h and "спеціальн" in h:
                col["specialty_code"] = i
            elif "група" in h:
                col["group_name"] = i
            elif "курс" in h:
                col["course"] = i

        if "faculty_name" not in col or "group_name" not in col:
            self.errors.append(f"Не знайдено обовʼязкові стовпці (Факультет, Група). Заголовки: {raw_headers}")
            return

        for row_idx, row in enumerate(self.rows_raw[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue
            try:
                self.preview_rows.append({
                    "faculty_name": row[col.get("faculty_name", 0)].strip(),
                    "faculty_code": row[col.get("faculty_code", col.get("faculty_name", 0))].strip(),
                    "specialty_name": row[col.get("specialty_name", 0)].strip() if "specialty_name" in col else "",
                    "specialty_code": row[col.get("specialty_code", 0)].strip() if "specialty_code" in col else "",
                    "group_name": row[col["group_name"]].strip(),
                    "course": row[col.get("course", 0)].strip() if "course" in col else "1",
                })
            except IndexError:
                self.errors.append(f"Рядок {row_idx}: невірний формат.")

    def _parse_disciplines(self, raw_headers):
        col = {}
        for i, h in enumerate(raw_headers):
            if "назва" in h or "дисциплін" in h and "код" not in h:
                col["name"] = i
            if "код" in h:
                col["code"] = i

        if "name" not in col or "code" not in col:
            self.errors.append(f"Не знайдено стовпці «Назва дисципліни» та «Код». Заголовки: {raw_headers}")
            return

        for row_idx, row in enumerate(self.rows_raw[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue
            try:
                self.preview_rows.append({
                    "name": row[col["name"]].strip(),
                    "code": row[col["code"]].strip(),
                })
            except IndexError:
                self.errors.append(f"Рядок {row_idx}: невірний формат.")

    def execute(self):
        if self.import_type == "disciplines":
            return self._exec_disciplines()
        return self._exec_structure()

    def _exec_disciplines(self):
        for row in self.preview_rows:
            _, created = Discipline.objects.get_or_create(
                code=row["code"], defaults={"name": row["name"]}
            )
            if created:
                self.results["created"] += 1
            else:
                self.results["skipped"] += 1
        return self.results

    def _exec_structure(self):
        for row in self.preview_rows:
            faculty, _ = Faculty.objects.get_or_create(
                code=row["faculty_code"] or _transliterate(row["faculty_name"])[:20],
                defaults={"name": row["faculty_name"]},
            )

            specialty = None
            if row["specialty_name"]:
                specialty, _ = Specialty.objects.get_or_create(
                    faculty=faculty,
                    code=row["specialty_code"] or _transliterate(row["specialty_name"])[:20],
                    defaults={"name": row["specialty_name"]},
                )

            if row["group_name"] and specialty:
                course = int(row["course"]) if row["course"].isdigit() else 1
                _, created = Group.objects.get_or_create(
                    specialty=specialty,
                    name=row["group_name"],
                    defaults={"course": course},
                )
                if created:
                    self.results["created"] += 1
                else:
                    self.results["skipped"] += 1
            else:
                self.results["created"] += 1  # Факультет/спеціальність створено

        return self.results


# ═══════════════════════════════════════════════════════════════════
# 3. ІМПОРТ ЖУРНАЛУ ОЦІНОК
# ═══════════════════════════════════════════════════════════════════

class GradebookImporter:
    """
    Очікуваний формат:
    Рядок 1: заголовки стовпців (Студент | Лекція 1 | Лекція 2 | ... | Лаб 1 | ...)
    Рядок 2: макс. оцінки (Макс. оцінка | 10 | 10 | 20 | ...)
    Рядки 3+: студенти (Іванов І.І. | 8 | н | 15 | ...)
    """

    def __init__(self, uploaded_file, assignment_id=None):
        self.rows_raw = _read_file(uploaded_file)
        self.assignment_id = assignment_id
        self.errors = []
        self.preview_rows = []
        self.column_lessons = []  # [(lesson_type, order_number), ...]
        self.max_grades = []
        self.results = {"grades_saved": 0, "absent_saved": 0, "max_grades_saved": 0, "errors": []}
        self._parse()

    def _parse(self):
        if len(self.rows_raw) < 3:
            self.errors.append("Файл має містити щонайменше 3 рядки (заголовки, макс. оцінки, студенти).")
            return

        # Рядок 1: заголовки — визначити тип і номер заняття
        headers = self.rows_raw[0]
        for i, h in enumerate(headers[1:], start=1):  # Перший стовпець — «Студент»
            h_lower = h.strip().lower()
            lesson_type = None
            order = None

            if "лекц" in h_lower or "lecture" in h_lower:
                lesson_type = "lecture"
            elif "практ" in h_lower or "practice" in h_lower:
                lesson_type = "practice"
            elif "лаб" in h_lower:
                lesson_type = "lab"

            # Витягнути номер
            nums = re.findall(r"\d+", h)
            if nums:
                order = int(nums[0])

            if lesson_type and order:
                self.column_lessons.append((i, lesson_type, order))
            elif h.strip():
                # Спробувати по позиції, якщо заголовок — просто число
                if h.strip().isdigit():
                    self.column_lessons.append((i, None, int(h.strip())))
                else:
                    self.errors.append(f"Стовпець {i + 1} «{h}»: не вдалося визначити тип заняття.")

        if not self.column_lessons:
            self.errors.append("Не знайдено жодного стовпця із заняттями.")
            return

        # Рядок 2: макс. оцінки
        max_row = self.rows_raw[1]
        for col_idx, lt, order in self.column_lessons:
            try:
                val = max_row[col_idx].strip()
                self.max_grades.append(int(val) if val.isdigit() else None)
            except IndexError:
                self.max_grades.append(None)

        # Рядки 3+: студенти
        for row_idx, row in enumerate(self.rows_raw[2:], start=3):
            if not any(cell.strip() for cell in row):
                continue
            student_name = row[0].strip() if row else ""
            if not student_name:
                continue

            grades = []
            for j, (col_idx, lt, order) in enumerate(self.column_lessons):
                try:
                    val = row[col_idx].strip()
                except IndexError:
                    val = ""
                grades.append(val)

            self.preview_rows.append({
                "student_name": student_name,
                "grades": grades,
            })

    def execute(self):
        """Виконує імпорт оцінок у вказаний TeacherAssignment."""
        if not self.assignment_id:
            self.results["errors"].append("Не вказано журнал (TeacherAssignment).")
            return self.results

        try:
            assignment = TeacherAssignment.objects.get(pk=self.assignment_id)
        except TeacherAssignment.DoesNotExist:
            self.results["errors"].append("Журнал не знайдено.")
            return self.results

        # Зіставити стовпці з Lesson-записами
        lessons_qs = assignment.lessons.order_by("lesson_type", "order_number")
        lesson_map = {}  # (lesson_type, order_number) -> Lesson
        for lesson in lessons_qs:
            lesson_map[(lesson.lesson_type, lesson.order_number)] = lesson

        # Зіставити стовпці → Lesson
        col_to_lesson = []
        for col_idx, lt, order in self.column_lessons:
            if lt:
                lesson = lesson_map.get((lt, order))
            else:
                # Якщо тип не визначено, шукаємо за порядковим номером серед усіх
                lesson = None
                for key, l in lesson_map.items():
                    if key[1] == order:
                        lesson = l
                        break
            col_to_lesson.append(lesson)

        # Зберегти макс. оцінки
        for j, lesson in enumerate(col_to_lesson):
            if lesson and j < len(self.max_grades) and self.max_grades[j] is not None:
                lesson.max_grade = self.max_grades[j]
                lesson.save(update_fields=["max_grade"])
                self.results["max_grades_saved"] += 1

        # Зберегти оцінки студентів
        students_qs = Student.objects.filter(
            group=assignment.group, is_active=True
        ).select_related("user")

        # Побудувати словник для пошуку студентів за прізвищем
        student_lookup = {}
        for s in students_qs:
            # Ключ: «Прізвище І.» або повне ПІБ
            full = f"{s.user.last_name} {s.user.first_name}"
            short = f"{s.user.last_name} {s.user.first_name[:1]}."
            student_lookup[full.lower()] = s
            student_lookup[short.lower()] = s
            student_lookup[s.user.last_name.lower()] = s
            student_lookup[s.record_book_number.lower()] = s

        for row in self.preview_rows:
            name = row["student_name"].lower().strip()
            student = student_lookup.get(name)
            if not student:
                # Спробувати часткове зіставлення
                for key, s in student_lookup.items():
                    if name in key or key in name:
                        student = s
                        break

            if not student:
                self.results["errors"].append(f"Студент «{row['student_name']}» не знайдений.")
                continue

            for j, val in enumerate(row["grades"]):
                lesson = col_to_lesson[j] if j < len(col_to_lesson) else None
                if not lesson:
                    continue

                val_lower = val.lower().strip()

                if val_lower in ("н", "n", "absent"):
                    # Відсутність
                    Attendance.objects.update_or_create(
                        student=student, lesson=lesson,
                        defaults={"status": Attendance.Status.ABSENT},
                    )
                    Grade.objects.filter(
                        student=student, lesson=lesson, grade_type=Grade.GradeType.CURRENT
                    ).delete()
                    self.results["absent_saved"] += 1

                elif val.isdigit():
                    grade_value = int(val)
                    Grade.objects.update_or_create(
                        student=student, lesson=lesson,
                        grade_type=Grade.GradeType.CURRENT,
                        defaults={"value": grade_value},
                    )
                    Attendance.objects.filter(
                        student=student, lesson=lesson, status=Attendance.Status.ABSENT
                    ).delete()
                    self.results["grades_saved"] += 1

                # Порожня клітинка — пропускаємо

        return self.results
