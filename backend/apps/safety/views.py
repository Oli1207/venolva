from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.feed.models import Post

from .models import Block, ContentReport


class BlocksView(APIView):
    """GET /api/blocks/ : mes membres bloqués. POST {user} : bloquer quelqu'un."""

    def get(self, request):
        rows = Block.objects.filter(blocker=request.user).select_related("blocked")
        return Response([{"id": b.blocked_id, "display_name": b.blocked.display_name, "initials": b.blocked.initials, "blocked_at": b.created_at} for b in rows])

    def post(self, request):
        target = get_object_or_404(User, pk=request.data.get("user"), is_active=True)
        if target == request.user:
            return Response({"detail": "Tu ne peux pas te bloquer toi-même."}, status=status.HTTP_400_BAD_REQUEST)
        if target.is_staff:
            return Response({"detail": "Les comptes de l'équipe ne se bloquent pas : utilise « Signaler »."}, status=status.HTTP_400_BAD_REQUEST)
        Block.objects.get_or_create(blocker=request.user, blocked=target)
        return Response({"id": target.id}, status=status.HTTP_201_CREATED)


class BlockDetailView(APIView):
    def delete(self, request, pk):
        Block.objects.filter(blocker=request.user, blocked_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportView(APIView):
    """POST /api/content-reports/ {kind: user|post, target, reason, detail}"""

    def post(self, request):
        kind, reason = request.data.get("kind"), request.data.get("reason")
        if kind not in dict(ContentReport.Kind.choices):
            return Response({"kind": ["Type inconnu."]}, status=status.HTTP_400_BAD_REQUEST)
        if reason not in dict(ContentReport.Reason.choices):
            return Response({"reason": ["Choisis un motif."]}, status=status.HTTP_400_BAD_REQUEST)
        detail = str(request.data.get("detail", ""))[:300]
        if kind == "user":
            target = get_object_or_404(User, pk=request.data.get("target"))
            if target == request.user:
                return Response({"detail": "Tu ne peux pas te signaler toi-même."}, status=status.HTTP_400_BAD_REQUEST)
            fields = {"user": target}
        else:
            target = get_object_or_404(Post, pk=request.data.get("target"))
            if target.author_id == request.user.pk:
                return Response({"detail": "C'est ta propre publication."}, status=status.HTTP_400_BAD_REQUEST)
            fields = {"post": target}
        try:
            with transaction.atomic():
                ContentReport.objects.create(reporter=request.user, kind=kind, reason=reason, detail=detail, **fields)
        except IntegrityError:
            return Response({"detail": "Tu as déjà signalé cela."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Merci, l'équipe va examiner ce signalement."}, status=status.HTTP_201_CREATED)
