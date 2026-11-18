from django.urls import path

from . import views

urlpatterns = [
    path("blocks/", views.BlocksView.as_view()),
    path("blocks/<uuid:pk>/", views.BlockDetailView.as_view()),
    path("content-reports/", views.ReportView.as_view()),
]
