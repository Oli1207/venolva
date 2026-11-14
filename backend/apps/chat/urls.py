from django.urls import path

from .views import ConversationListView, ConversationStartView, MessageListCreateView

urlpatterns = [
    path("conversations/", ConversationListView.as_view()),
    path("conversations/start/", ConversationStartView.as_view()),
    path("conversations/<int:pk>/messages/", MessageListCreateView.as_view()),
]
