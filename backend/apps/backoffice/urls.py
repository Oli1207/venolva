from django.urls import path

from . import views as v

urlpatterns = [
    path("admin/dashboard/", v.DashboardView.as_view()),
    path("admin/settings/", v.SettingsView.as_view()),
    path("admin/audit/", v.AuditView.as_view()),
    path("admin/commissions/", v.CommissionsView.as_view()),
    path("admin/commissions/<uuid:pk>/", v.CommissionDetailView.as_view()),
    path("admin/payments/", v.PaymentsView.as_view()),
    path("admin/payments/<uuid:pk>/<str:action>/", v.PaymentActionView.as_view()),
    path("admin/webhooks/", v.WebhooksView.as_view()),
    path("admin/payees/", v.PayeesView.as_view()),
    path("admin/payouts/", v.PayoutsView.as_view()),
    path("admin/payouts/export/", v.PayoutsExportView.as_view()),
    path("admin/payouts/<uuid:pk>/", v.PayoutDetailView.as_view()),
    path("admin/payouts/<uuid:pk>/<str:action>/", v.PayoutActionView.as_view()),
    path("admin/pro-applications/", v.ProApplicationsView.as_view()),
    path("admin/pro-applications/<uuid:pk>/<str:action>/", v.ProApplicationActionView.as_view()),
    path("admin/gyms/", v.GymsView.as_view()),
    path("admin/gyms/<uuid:pk>/", v.GymDetailView.as_view()),
    path("admin/reports/", v.ReportsView.as_view()),
    path("admin/reports/<uuid:pk>/<str:action>/", v.ReportActionView.as_view()),
    path("admin/users/", v.UsersView.as_view()),
    path("admin/users/<uuid:pk>/", v.UserDetailView.as_view()),
]
