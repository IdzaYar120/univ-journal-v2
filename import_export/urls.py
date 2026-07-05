from django.urls import path

from . import views

app_name = "import_export"

urlpatterns = [
    path("", views.import_hub, name="import_hub"),
    path("students/", views.import_students, name="import_students"),
    path("structure/", views.import_structure, name="import_structure"),
    path("gradebook/", views.import_gradebook, name="import_gradebook"),
    path("export-excel/<int:assignment_id>/", views.export_gradebook_excel, name="export_gradebook_excel"),
]
