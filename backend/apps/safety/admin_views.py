from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from apps.backoffice.models import audit
from apps.backoffice.views import AdminView, bad, page, person
from apps.notifications.services import notify

from .models import ContentReport


def row(r: ContentReport) -> dict:
    post = r.post
    return {
        "id": r.id, "kind": r.kind, "reason": r.reason, "reason_label": r.get_reason_display(), "detail": r.detail,
        "reporter": person(r.reporter), "handled": r.handled, "created_at": r.created_at,
        "user": person(r.user) if r.user_id else None,
        "post": {"id": post.id, "title": post.title, "body": post.body[:300], "hidden": post.hidden, "author": person(post.author)} if post else None,
        "same_target_reports": (ContentReport.objects.filter(user_id=r.user_id).count() if r.kind == "user" else ContentReport.objects.filter(post_id=r.post_id).count()),
    }


class AdminReportsView(AdminView):
    """GET /api/admin/reports/?handled=0|1 : les signalements, les plus récents d'abord."""

    def get(self, request):
        qs = ContentReport.objects.select_related("reporter", "user", "post", "post__author")
        qs = qs.filter(handled=request.query_params.get("handled") == "1")
        return page(request, qs, row)


class AdminReportActionView(AdminView):
    """POST /api/admin/reports/<id>/<action>/ avec action = dismiss | hide_post | suspend_user."""

    def post(self, request, pk, action):
        r = get_object_or_404(ContentReport.objects.select_related("post", "user", "post__author"), pk=pk)
        if r.handled:
            return bad("Ce signalement est déjà traité.")
        if action == "dismiss":
            pass
        elif action == "hide_post":
            if not r.post_id:
                return bad("Ce signalement ne concerne pas une publication.")
            r.post.hidden = True
            r.post.save(update_fields=["hidden"])
            notify(r.post.author, "post_hidden", "Une de tes publications a été masquée", "Elle ne respectait pas les règles de Djinzin.", "")
        elif action == "suspend_user":
            target = r.user if r.kind == "user" else r.post.author
            if target.is_staff:
                return bad("Un compte de l'équipe ne se suspend pas ici.")
            target.is_active = False
            target.save(update_fields=["is_active"])
        else:
            return bad("Action inconnue.")
        # un même contenu signalé plusieurs fois : une décision les clôt tous
        siblings = ContentReport.objects.filter(handled=False, kind=r.kind, **({"user_id": r.user_id} if r.kind == "user" else {"post_id": r.post_id}))
        siblings.update(handled=True)
        audit(request.user, f"report.{action}", f"report:{r.id}", kind=r.kind)
        return Response({"ok": True})
