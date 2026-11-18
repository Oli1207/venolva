from django.urls import path

from . import admin_views as a
from . import views as v

urlpatterns = [
    path("features/", v.FeaturesView.as_view()),
    path("features/live/", v.LiveFeaturesView.as_view()),
    path("features/mine/", v.MyFeaturesView.as_view()),
    path("features/<uuid:pk>/<str:event>/", v.FeatureEventView.as_view()),
    path("admin/features/", a.AdminFeaturesView.as_view()),
    path("admin/features/<uuid:pk>/<str:action>/", a.AdminFeatureActionView.as_view()),
]
