from django.urls import path

from . import views

urlpatterns = [
    path("my/earnings/", views.EarningsView.as_view()),
    path("my/payout-account/", views.PayoutAccountView.as_view()),
    path("payments/", views.PaymentCreateView.as_view()),
    path("payments/methods/", views.MethodsView.as_view()),
    path("payments/webhooks/paystack/", views.PaystackWebhookView.as_view()),
    path("payments/webhooks/jeko/", views.JekoWebhookView.as_view()),
    path("payments/<str:reference>/", views.PaymentDetailView.as_view()),
    path("payments/<str:reference>/verify/", views.PaymentVerifyView.as_view()),
]
