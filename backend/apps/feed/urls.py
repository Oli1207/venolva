from django.urls import path

from .views import PostJoinView, PostListCreateView

urlpatterns = [
    path("posts/", PostListCreateView.as_view()),
    path("posts/<int:pk>/join/", PostJoinView.as_view()),
]
