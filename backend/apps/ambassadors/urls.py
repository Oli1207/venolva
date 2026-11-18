from django.urls import path

from . import views as v

urlpatterns = [
    path("admin/ambassadors/", v.AmbassadorsView.as_view()),
    path("admin/ambassadors/<uuid:pk>/", v.AmbassadorDetailView.as_view()),
    path("admin/ambassadors/<uuid:pk>/contracts/", v.ContractCreateView.as_view()),
    path("admin/ambassadors/<uuid:pk>/statements/", v.StatementCreateView.as_view()),
    path("admin/contracts/<uuid:pk>/<str:action>/", v.ContractActionView.as_view()),
    path("admin/statements/<uuid:pk>/<str:action>/", v.StatementActionView.as_view()),
    path("my/ambassador/", v.MyAmbassadorView.as_view()),
]
