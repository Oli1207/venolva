from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.models import audit
from apps.backoffice.views import AdminView, bad, page, person

from .models import Feature
from .services import PromoError, approve, create_direct, end_now, payload, reject


def row(f: Feature) -> dict:
    p = payload(f)
    return {
        "id": f.id, "kind": f.kind, "title": p["title"] if p else "Contenu supprimé ou indisponible", "link": p["link"] if p else None,
        "requested_by": person(f.requested_by), "status": f.status, "sponsored": f.sponsored, "scope_commune": f.scope_commune,
        "requested_days": f.requested_days, "starts_at": f.starts_at, "ends_at": f.ends_at, "views": f.views, "clicks": f.clicks,
        "note": f.note, "live": bool(f.status == "approved" and f.ends_at and f.ends_at > timezone.now()), "price_fcfa": f.price_fcfa,
    }


class AdminFeaturesView(AdminView):
    def get(self, request):
        qs = Feature.objects.select_related("requested_by", "post", "post__author", "pro", "gym", "listing")
        st = request.query_params.get("status", "pending")
        if st != "all":
            qs = qs.filter(status=st)
        return page(request, qs, row)

    def post(self, request):
        """L'équipe met un contenu à la une directement : {kind, target, days, commune?, sponsored?}."""
        d = request.data
        try:
            f = create_direct(request.user, str(d.get("kind", "")), d.get("target"), int(d.get("days", 7)), str(d.get("commune", "")), bool(d.get("sponsored", False)), str(d.get("note", "")))
        except (PromoError, TypeError, ValueError) as exc:
            return bad(str(exc) if isinstance(exc, PromoError) else "Durée invalide.")
        audit(request.user, "feature.create", f"feature:{f.id}", kind=f.kind, days=f.requested_days)
        return Response(row(f), status=status.HTTP_201_CREATED)


class AdminFeatureActionView(AdminView):
    def post(self, request, pk, action):
        f = get_object_or_404(Feature, pk=pk)
        try:
            if action == "approve":
                days = request.data.get("days")
                approve(f, request.user, days=days if isinstance(days, int) and not isinstance(days, bool) else None)
                audit(request.user, "feature.approve", f"feature:{f.id}", days=(f.ends_at - f.starts_at).days)
            elif action == "reject":
                reject(f, request.user, str(request.data.get("note", "")))
                audit(request.user, "feature.reject", f"feature:{f.id}", note=f.note)
            elif action == "end":
                end_now(f, request.user)
                audit(request.user, "feature.end", f"feature:{f.id}")
            else:
                return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        except PromoError as exc:
            return bad(str(exc))
        return Response(row(f))
