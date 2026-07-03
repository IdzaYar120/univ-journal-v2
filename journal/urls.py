from django.urls import path

from . import views

app_name = "journal"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("assignment/<int:assignment_id>/", views.assignment_detail, name="assignment_detail"),
    path("assignment/<int:assignment_id>/matrix/", views.gradebook_matrix, name="gradebook_matrix"),
    path("assignment/<int:assignment_id>/save-cell/", views.save_cell, name="save_cell"),
    path("my-grades/", views.my_grades, name="my_grades"),
]
