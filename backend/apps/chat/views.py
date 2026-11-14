from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from .models import Conversation, Message
from .services import get_or_create_conversation


class MessageSerializer(serializers.ModelSerializer):
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "body", "created_at", "mine"]

    def get_mine(self, obj):
        return obj.sender_id == self.context["request"].user.pk


class ConversationListView(ListAPIView):
    """GET /api/conversations/ : mes discussions, la plus récente d'abord, avec le nombre de non lus."""

    pagination_class = None

    def list(self, request, *args, **kwargs):
        me = request.user
        convs = (
            Conversation.objects.filter(Q(user_a=me) | Q(user_b=me))
            .select_related("user_a", "user_b", "meetup")
            .annotate(unread=Count("messages", filter=~Q(messages__sender=me) & Q(messages__read_at__isnull=True)))
        )
        out = []
        for c in convs:
            other = c.other(me)
            last = c.messages.order_by("-created_at").first()
            out.append(
                {
                    "id": c.id,
                    "other": {
                        "id": other.id,
                        "display_name": other.display_name,
                        "initials": other.initials,
                        "pro_type": other.pro_type,
                        "pro_verified": other.pro_verified,
                    },
                    "last_message": last.body if last else "",
                    "last_at": last.created_at if last else c.updated_at,
                    "unread": c.unread,
                    "meetup": c.meetup_id,
                }
            )
        return Response(out)


class ConversationStartView(APIView):
    """POST /api/conversations/ {user: <id>} : ouvre (ou retrouve) la discussion avec quelqu'un."""

    def post(self, request):
        other = get_object_or_404(User, pk=request.data.get("user"), is_active=True)
        if other == request.user:
            return Response({"detail": "Tu ne peux pas t'écrire à toi-même."}, status=status.HTTP_400_BAD_REQUEST)
        conv = get_or_create_conversation(request.user, other)
        return Response({"id": conv.id}, status=status.HTTP_201_CREATED)


class MessageListCreateView(APIView):
    """GET /api/conversations/<id>/messages/?after=<id> (sondage) et POST {body}."""

    def _conv(self, request, pk):
        conv = get_object_or_404(Conversation, pk=pk)
        if not conv.involves(request.user):
            # 404 plutôt que 403 : on ne révèle pas l'existence d'une discussion privée.
            from django.http import Http404

            raise Http404
        return conv

    def get(self, request, pk):
        conv = self._conv(request, pk)
        qs = conv.messages.all()
        after = request.query_params.get("after")
        if after and after.isdigit():
            qs = qs.filter(id__gt=int(after))
        msgs = list(qs.order_by("created_at")[:200])
        conv.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
        return Response(MessageSerializer(msgs, many=True, context={"request": request}).data)

    def post(self, request, pk):
        conv = self._conv(request, pk)
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response({"detail": "Message vide."}, status=status.HTTP_400_BAD_REQUEST)
        if len(body) > 1000:
            return Response({"detail": "Message trop long (1000 caractères)."}, status=status.HTTP_400_BAD_REQUEST)
        msg = Message.objects.create(conversation=conv, sender=request.user, body=body)
        conv.save(update_fields=["updated_at"])
        return Response(MessageSerializer(msg, context={"request": request}).data, status=status.HTTP_201_CREATED)
