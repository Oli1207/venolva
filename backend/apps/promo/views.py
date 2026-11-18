from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.backoffice.config import cfg

from .models import Feature
from .services import PromoError, live_qs, payload, record, request_feature


class LiveFeaturesView(APIView):
    """GET /api/features/live/?commune= : le bandeau « À la une ». Par défaut, celui de ma commune."""

    def get(self, request):
        commune = request.query_params.get("commune", request.user.commune or "")
        rows = []
        for f in live_qs(commune).order_by("starts_at")[: cfg().featured_slots]:
            p = payload(f)
            if p:
                rows.append(p)
        return Response(rows)


def mine_row(f: Feature) -> dict:
    p = payload(f)
    return {
        "id": f.id, "kind": f.kind, "title": p["title"] if p else "Contenu supprimé", "status": f.status, "sponsored": f.sponsored,
        "starts_at": f.starts_at, "ends_at": f.ends_at, "requested_days": f.requested_days, "views": f.views, "clicks": f.clicks,
        "note": f.note, "live": bool(f.status == "approved" and f.ends_at and f.ends_at > timezone.now()),
    }


class FeaturesView(APIView):
    """POST {kind, target, days, commune?} : demander la mise à la une d'un de mes contenus."""

    def post(self, request):
        try:
            f = request_feature(request.user, str(request.data.get("kind", "")), request.data.get("target"), request.data.get("days", 7), str(request.data.get("commune", "")))
        except PromoError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(mine_row(f), status=status.HTTP_201_CREATED)


class MyFeaturesView(APIView):
    """GET /api/features/mine/ : mes demandes, avec leurs vues et leurs clics."""

    def get(self, request):
        s = cfg()
        rows = Feature.objects.filter(requested_by=request.user)[:50]
        return Response({"max_days": s.featured_max_days, "results": [mine_row(f) for f in rows]})


class FeatureEventView(APIView):
    def post(self, request, pk, event):
        if event not in ("seen", "click"):
            return Response({"detail": "Événement inconnu."}, status=status.HTTP_404_NOT_FOUND)
        get_object_or_404(Feature, pk=pk, status="approved")
        record(pk, request.user, "view" if event == "seen" else "click")
        return Response(status=status.HTTP_204_NO_CONTENT)
