from django.urls import path

from . import views

urlpatterns = [
    path("gyms/", views.GymListView.as_view()),
    path("gyms/<int:pk>/", views.GymDetailView.as_view()),
    path("gyms/<int:pk>/reviews/", views.GymReviewsView.as_view()),
    path("gym-plans/<int:pk>/request/", views.PlanRequestView.as_view()),
    path("gym-requests/", views.MyRequestsView.as_view()),
    path("gym-requests/<int:pk>/cancel/", views.MyRequestCancelView.as_view()),
    path("gym-classes/<int:pk>/<str:action>/", views.ClassBookView.as_view()),
    path("my/gym/", views.MyGymView.as_view()),
    path("my/gym/hours/", views.MyHoursView.as_view()),
    path("my/gym/plans/", views.MyPlansView.as_view()),
    path("my/gym/plans/<int:pk>/", views.MyPlanDetailView.as_view()),
    path("my/gym/classes/", views.MyClassesView.as_view()),
    path("my/gym/classes/<int:pk>/", views.MyClassDetailView.as_view()),
    path("my/gym/classes/<int:pk>/participants/", views.MyClassParticipantsView.as_view()),
    path("my/gym/requests/", views.MyGymRequestsView.as_view()),
    path("my/gym/requests/<int:pk>/<str:action>/", views.MyGymRequestActionView.as_view()),
]
