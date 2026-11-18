from django.urls import path

from . import views

urlpatterns = [
    path("pro/me/", views.ProMeView.as_view()),
    path("pro/apply/", views.ProApplyView.as_view()),
    path("pros/", views.ProListView.as_view()),
    path("pros/<uuid:pk>/", views.ProDetailView.as_view()),
    path("pros/<uuid:pk>/slots/", views.SlotsView.as_view()),
    path("my/services/", views.MyServicesView.as_view()),
    path("my/services/<uuid:pk>/", views.MyServiceDetailView.as_view()),
    path("my/availability/", views.MyAvailabilityView.as_view()),
    path("bookings/", views.BookingListCreateView.as_view()),
    path("bookings/<uuid:pk>/<str:action>/", views.BookingActionView.as_view()),
]
