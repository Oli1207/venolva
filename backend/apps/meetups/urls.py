from django.urls import path

from .views import MeetupActionView, MeetupListCreateView

urlpatterns = [
    path("meetups/", MeetupListCreateView.as_view()),
    path("meetups/<uuid:pk>/<str:action>/", MeetupActionView.as_view()),
]
