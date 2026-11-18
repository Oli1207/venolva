from django.urls import path

from . import views

urlpatterns = [
    path("posts/", views.PostListCreateView.as_view()),
    path("posts/<uuid:pk>/", views.PostDetailView.as_view()),
    path("posts/<uuid:pk>/join/", views.PostJoinView.as_view()),
    path("posts/<uuid:pk>/like/", views.PostLikeView.as_view()),
    path("feed/", views.FeedView.as_view()),
    path("feed/seen/", views.FeedSeenView.as_view()),
]
