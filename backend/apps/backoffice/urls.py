from django.urls import path

from . import views as v

urlpatterns = [
    path("admin/dashboard/", v.DashboardView.as_view()),
    path("admin/settings/", v.SettingsView.as_view()),
    path("admin/audit/", v.AuditView.as_view()),
    path("admin/commissions/", v.CommissionsView.as_view()),
    path("admin/commissions/<int:pk>/", v.CommissionDetailView.as_view()),
    path("admin/payments/", v.PaymentsView.as_view()),
    path("admin/payments/<int:pk>/<str:action>/", v.PaymentActionView.as_view()),
    path("admin/webhooks/", v.WebhooksView.as_view()),
    path("admin/payees/", v.PayeesView.as_view()),
    path("admin/payouts/", v.PayoutsView.as_view()),
    path("admin/payouts/export/", v.PayoutsExportView.as_view()),
    path("admin/payouts/<int:pk>/", v.PayoutDetailView.as_view()),
    path("admin/payouts/<int:pk>/<str:action>/", v.PayoutActionView.as_view()),
    path("admin/pro-applications/", v.ProApplicationsView.as_view()),
    path("admin/pro-applications/<int:pk>/<str:action>/", v.ProApplicationActionView.as_view()),
    path("admin/gyms/", v.GymsView.as_view()),
    path("admin/gyms/<int:pk>/", v.GymDetailView.as_view()),
    path("admin/reports/", v.ReportsView.as_view()),
    path("admin/reports/<int:pk>/<str:action>/", v.ReportActionView.as_view()),
    path("admin/users/", v.UsersView.as_view()),
    path("admin/users/<int:pk>/", v.UserDetailView.as_view()),
]
