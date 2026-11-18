from django.urls import path

from . import views

urlpatterns = [
    path("posts/", views.PostListCreateView.as_view()),
    path("posts/<int:pk>/", views.PostDetailView.as_view()),
    path("posts/<int:pk>/join/", views.PostJoinView.as_view()),
    path("posts/<int:pk>/like/", views.PostLikeView.as_view()),
    path("feed/", views.FeedView.as_view()),
    path("feed/seen/", views.FeedSeenView.as_view()),
]
