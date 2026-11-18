from django.urls import path

from . import views

urlpatterns = [
    path("listings/", views.ListingListCreateView.as_view()),
    path("listings/<uuid:pk>/", views.ListingDetailView.as_view()),
    path("listings/<uuid:pk>/photos/", views.ListingPhotoView.as_view()),
    path("listings/<uuid:pk>/contact/", views.ListingContactView.as_view()),
    path("listings/<uuid:pk>/report/", views.ListingReportView.as_view()),
]
