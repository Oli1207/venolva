from datetime import timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.services import get_or_create_conversation
from apps.gyms.models import Gym
from apps.notifications.services import notify
from apps.safety.services import blocked_ids

from .models import Meetup
from .serializers import MeetupCreateSerializer, MeetupSerializer

ARRIVAL_WINDOW_BEFORE = timedelta(hours=2)
ARRIVAL_WINDOW_AFTER = timedelta(hours=3)


def create_meetup(organizer, partner, starts_at, gym=None, focus=""):
    """Crée une séance en attente et ouvre la discussion entre les deux personnes."""
    meetup = Meetup.objects.create(organizer=organizer, partner=partner, starts_at=starts_at, gym=gym, focus=focus)
    conv = get_or_create_conversation(organizer, partner)
    conv.meetup = meetup
    conv.save(update_fields=["meetup", "updated_at"])
    notify(partner, "meetup_proposed", f"{organizer.display_name or 'Un membre'} te propose une séance", focus, "/seances")
    return meetup


class MeetupListCreateView(ListAPIView):
    serializer_class = MeetupSerializer
    pagination_class = None

    def get_queryset(self):
        u = self.request.user
        qs = Meetup.objects.filter(Q(organizer=u) | Q(partner=u)).select_related("organizer", "partner", "gym")
        when = self.request.query_params.get("when")
        now = timezone.now()
        if when == "past":
            qs = qs.filter(starts_at__lt=now).order_by("-starts_at")
        elif when == "upcoming":
            qs = qs.filter(starts_at__gte=now).exclude(status=Meetup.Status.CANCELLED)
        return qs

    def post(self, request):
        ser = MeetupCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        if data["partner"].pk in blocked_ids(request.user):
            return Response({"partner": ["Cette personne n'est pas disponible."]}, status=status.HTTP_400_BAD_REQUEST)
        gym = Gym.objects.filter(pk=data.get("gym")).first() if data.get("gym") else None
        meetup = create_meetup(request.user, data["partner"], data["starts_at"], gym, data.get("focus", ""))
        return Response(MeetupSerializer(meetup, context={"request": request}).data, status=status.HTTP_201_CREATED)


class MeetupActionView(APIView):
    """POST /api/meetups/<id>/<action>/ avec action = respond | cancel | arrive."""

    def post(self, request, pk, action):
        meetup = get_object_or_404(Meetup, pk=pk)
        if not meetup.involves(request.user):
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        handler = getattr(self, f"do_{action}", None)
        if handler is None:
            return Response({"detail": "Action inconnue."}, status=status.HTTP_404_NOT_FOUND)
        error = handler(request, meetup)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        meetup.refresh_from_db()
        return Response(MeetupSerializer(meetup, context={"request": request}).data)

    def do_respond(self, request, meetup):
        if meetup.partner_id != request.user.pk:
            return "Seule la personne invitée peut répondre."
        if meetup.status != Meetup.Status.PENDING:
            return "Cette séance a déjà reçu une réponse."
        accept = request.data.get("accept")
        if not isinstance(accept, bool):
            return "Indique accept: true ou false."
        meetup.status = Meetup.Status.CONFIRMED if accept else Meetup.Status.CANCELLED
        meetup.save(update_fields=["status"])
        notify(meetup.organizer, "meetup_answer", f"{request.user.display_name or 'Ton binôme'} a {'accepté' if accept else 'refusé'} ta séance", "", "/seances")

    def do_cancel(self, request, meetup):
        if meetup.status in (Meetup.Status.DONE, Meetup.Status.CANCELLED):
            return "Cette séance est déjà terminée ou annulée."
        meetup.status = Meetup.Status.CANCELLED
        meetup.save(update_fields=["status"])
        notify(meetup.other(request.user), "meetup_cancelled", f"{request.user.display_name or 'Ton binôme'} a annulé la séance", "", "/seances")

    def do_arrive(self, request, meetup):
        if meetup.status != Meetup.Status.CONFIRMED:
            return "La séance doit être confirmée."
        now = timezone.now()
        if not (meetup.starts_at - ARRIVAL_WINDOW_BEFORE <= now <= meetup.starts_at + ARRIVAL_WINDOW_AFTER):
            return "Tu peux signaler ton arrivée 2 h avant et jusqu'à 3 h après l'heure prévue."
        field = "organizer_arrived_at" if meetup.organizer_id == request.user.pk else "partner_arrived_at"
        if getattr(meetup, field) is None:
            setattr(meetup, field, now)
        if meetup.organizer_arrived_at and meetup.partner_arrived_at:
            meetup.status = Meetup.Status.DONE
        meetup.save()
