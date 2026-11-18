from django.urls import path

from . import views as v

urlpatterns = [
    path("admin/ambassadors/", v.AmbassadorsView.as_view()),
    path("admin/ambassadors/<int:pk>/", v.AmbassadorDetailView.as_view()),
    path("admin/ambassadors/<int:pk>/contracts/", v.ContractCreateView.as_view()),
    path("admin/ambassadors/<int:pk>/statements/", v.StatementCreateView.as_view()),
    path("admin/contracts/<int:pk>/<str:action>/", v.ContractActionView.as_view()),
    path("admin/statements/<int:pk>/<str:action>/", v.StatementActionView.as_view()),
    path("my/ambassador/", v.MyAmbassadorView.as_view()),
]
