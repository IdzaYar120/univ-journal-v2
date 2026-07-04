from django.urls import path

from . import views

app_name = "import_export"

urlpatterns = [
    path("", views.import_hub, name="import_hub"),
    path("students/", views.import_students, name="import_students"),
    path("structure/", views.import_structure, name="import_structure"),
    path("gradebook/", views.import_gradebook, name="import_gradebook"),
]
