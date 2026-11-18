from django.urls import path

from . import admin_views as a

urlpatterns = [
    path("admin/content-reports/", a.AdminReportsView.as_view()),
    path("admin/content-reports/<int:pk>/<str:action>/", a.AdminReportActionView.as_view()),
]
