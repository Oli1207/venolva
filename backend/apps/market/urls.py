from django.urls import path

from . import views

urlpatterns = [
    path("listings/", views.ListingListCreateView.as_view()),
    path("listings/<int:pk>/", views.ListingDetailView.as_view()),
    path("listings/<int:pk>/photos/", views.ListingPhotoView.as_view()),
    path("listings/<int:pk>/contact/", views.ListingContactView.as_view()),
    path("listings/<int:pk>/report/", views.ListingReportView.as_view()),
]
