from django.urls import path

from .views import MatchListView, MemberDetailView

urlpatterns = [
    path("matches/", MatchListView.as_view()),
    path("members/<uuid:pk>/", MemberDetailView.as_view()),
]
