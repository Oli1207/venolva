from django.urls import path

from .views import MatchListView, MemberDetailView

urlpatterns = [
    path("matches/", MatchListView.as_view()),
    path("members/<int:pk>/", MemberDetailView.as_view()),
]
