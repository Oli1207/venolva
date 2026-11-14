from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import MeView, OtpRequestView, OtpVerifyView

urlpatterns = [
    path("otp/request/", OtpRequestView.as_view()),
    path("otp/verify/", OtpVerifyView.as_view()),
    path("refresh/", TokenRefreshView.as_view()),
    path("me/", MeView.as_view()),
]
