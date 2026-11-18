from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationsView(APIView):
    """GET /api/notifications/ : les 40 dernières, avec le nombre de non lues."""

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        rows = qs[:40]
        return Response(
            {
                "unread": qs.filter(read_at__isnull=True).count(),
                "results": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "created_at": n.created_at, "read": n.read_at is not None} for n in rows],
            }
        )


class NotificationsReadView(APIView):
    """POST /api/notifications/read/ {all: true} ou {ids: [..]}"""

    def post(self, request):
        qs = Notification.objects.filter(user=request.user, read_at__isnull=True)
        if request.data.get("all") is True:
            qs.update(read_at=timezone.now())
        else:
            ids = request.data.get("ids")
            if isinstance(ids, list):
                qs.filter(pk__in=[i for i in ids if isinstance(i, int)]).update(read_at=timezone.now())
        return Response({"unread": Notification.objects.filter(user=request.user, read_at__isnull=True).count()})
