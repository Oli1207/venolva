from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.gyms.urls")),
    path("api/", include("apps.matching.urls")),
    path("api/", include("apps.meetups.urls")),
    path("api/", include("apps.chat.urls")),
    path("api/", include("apps.feed.urls")),
    path("api/", include("apps.pros.urls")),
    path("api/", include("apps.market.urls")),
    path("api/", include("apps.payments.urls")),
    path("api/", include("apps.backoffice.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # sert les photos en développement seulement
