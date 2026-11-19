from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

def health(_request):
    """Sonde pour le serveur : l'application répond et la base de données aussi."""
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        return JsonResponse({"ok": False}, status=503)
    return JsonResponse({"ok": True})


urlpatterns = [
    path("django-admin/", admin.site.urls),  # hors /admin, réservé à l'espace équipe de l'application
    path("api/health/", health),
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
    path("api/", include("apps.ambassadors.urls")),
    path("api/", include("apps.safety.urls")),
    path("api/", include("apps.safety.admin_urls")),
    path("api/", include("apps.promo.urls")),
    path("api/", include("apps.notifications.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # sert les photos en développement seulement
