from datetime import date

from django.db import transaction
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.chat.services import get_or_create_conversation
from apps.gyms.models import Gym

from . import services as slots
from .models import Availability, Booking, ProProfile, Service
from .serializers import (
    AvailabilitySerializer, BookingCreateSerializer, BookingSerializer, PersonSerializer, ProApplySerializer,
    ServiceSerializer,
)


class IsVerifiedPro(BasePermission):
    message = "Réservé aux professionnels vérifiés."

    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.pro_type and u.pro_verified)


def profile_payload(p: ProProfile) -> dict:
    return {
        "speciality": p.speciality,
        "bio": p.bio,
        "credential": p.credential,
        "gym": {"id": p.gym_id, "name": p.gym.name} if p.gym_id else None,
        "years_experience": p.years_experience,
        "status": p.status,
        "review_note": p.review_note,
    }


class ProMeView(APIView):
    """GET /api/pro/me/ : état de ma candidature (none, pending, approved, rejected)."""

    def get(self, request):
        p = ProProfile.objects.filter(user=request.user).select_related("gym").first()
        if not p:
            return Response({"status": "none", "pro_type": ""})
        return Response({"pro_type": request.user.pro_type, **profile_payload(p)})


class ProApplyView(APIView):
    """POST /api/pro/apply/ : envoyer ou mettre à jour ma candidature. Validation manuelle par l'équipe."""

    def post(self, request):
        ser = ProApplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        existing = ProProfile.objects.filter(user=request.user).first()
        if existing and existing.status == ProProfile.Status.APPROVED:
            return Response({"detail": "Ton compte pro est déjà validé."}, status=status.HTTP_400_BAD_REQUEST)
        gym = Gym.objects.filter(pk=d.get("gym")).first() if d.get("gym") else None
        with transaction.atomic():
            p, _ = ProProfile.objects.update_or_create(
                user=request.user,
                defaults=dict(
                    speciality=d.get("speciality", ""), bio=d.get("bio", ""), credential=d["credential"],
                    gym=gym, years_experience=d.get("years_experience"), status=ProProfile.Status.PENDING, review_note="",
                ),
            )
            request.user.pro_type = d["pro_type"]
            request.user.pro_verified = False
            request.user.save(update_fields=["pro_type", "pro_verified"])
        return Response({"pro_type": request.user.pro_type, **profile_payload(p)}, status=status.HTTP_201_CREATED)


class ProListView(APIView):
    """GET /api/pros/?type=coach&commune=Cocody&q=serge : professionnels validés."""

    def get(self, request):
        qs = (
            ProProfile.objects.filter(status=ProProfile.Status.APPROVED, user__pro_verified=True)
            .select_related("user", "gym")
            .annotate(
                min_price=Min("user__services__price", filter=Q(user__services__active=True)),
                done=Count("user__bookings_received", filter=Q(user__bookings_received__status="done"), distinct=True),
            )
        )
        t, commune, q = (request.query_params.get(k) for k in ("type", "commune", "q"))
        if t:
            qs = qs.filter(user__pro_type=t)
        if commune:
            qs = qs.filter(Q(user__commune__iexact=commune) | Q(gym__commune__iexact=commune))
        if q:
            qs = qs.filter(Q(user__display_name__icontains=q) | Q(speciality__icontains=q))
        out = [
            {
                "person": PersonSerializer(p.user).data,
                "speciality": p.speciality,
                "gym": p.gym.name if p.gym_id else None,
                "min_price": p.min_price,
                "sessions_done": p.done,
            }
            for p in qs.order_by("-done", "user__display_name")[:50]
            if p.min_price is not None
        ]
        return Response(out)


class ProDetailView(APIView):
    """GET /api/pros/<user_id>/ : profil public, services actifs et jours de disponibilité."""

    def get(self, request, pk):
        p = get_object_or_404(
            ProProfile.objects.select_related("user", "gym"), user_id=pk, status=ProProfile.Status.APPROVED, user__pro_verified=True
        )
        svcs = Service.objects.filter(owner=p.user, active=True).select_related("gym")
        days = sorted(set(Availability.objects.filter(pro=p.user).values_list("weekday", flat=True)))
        return Response(
            {
                "person": PersonSerializer(p.user).data,
                "speciality": p.speciality,
                "bio": p.bio,
                "years_experience": p.years_experience,
                "gym": {"id": p.gym_id, "name": p.gym.name} if p.gym_id else None,
                "sessions_done": Booking.objects.filter(pro=p.user, status="done").count(),
                "services": ServiceSerializer(svcs, many=True).data,
                "weekdays": days,
            }
        )


class SlotsView(APIView):
    """GET /api/pros/<user_id>/slots/?service=<id>&date=2026-11-17 : heures de début libres."""

    def get(self, request, pk):
        service = get_object_or_404(Service, pk=request.query_params.get("service") or 0, owner_id=pk, active=True, owner__pro_verified=True)
        try:
            day = date.fromisoformat(request.query_params.get("date", ""))
        except ValueError:
            return Response({"detail": "Date invalide (AAAA-MM-JJ)."}, status=status.HTTP_400_BAD_REQUEST)
        times = slots.free_slots(service.owner, service, day)
        return Response([t.isoformat() for t in times])


class MyServicesView(ListCreateAPIView):
    permission_classes = [IsVerifiedPro]
    serializer_class = ServiceSerializer
    pagination_class = None

    def get_queryset(self):
        return Service.objects.filter(owner=self.request.user).select_related("gym")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class MyServiceDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsVerifiedPro]
    serializer_class = ServiceSerializer

    def get_queryset(self):
        return Service.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance):
        # Un service déjà réservé reste dans l'historique : on le désactive au lieu de le supprimer.
        if instance.bookings.exists():
            instance.active = False
            instance.save(update_fields=["active"])
        else:
            instance.delete()


class MyAvailabilityView(APIView):
    """GET puis PUT /api/my/availability/ : le PUT remplace toute la semaine."""

    permission_classes = [IsVerifiedPro]

    def get(self, request):
        return Response(AvailabilitySerializer(Availability.objects.filter(pro=request.user), many=True).data)

    def put(self, request):
        ser = AvailabilitySerializer(data=request.data, many=True)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            Availability.objects.filter(pro=request.user).delete()
            Availability.objects.bulk_create([Availability(pro=request.user, **row) for row in ser.validated_data])
        return Response(AvailabilitySerializer(Availability.objects.filter(pro=request.user), many=True).data)


class BookingListCreateView(ListAPIView):
    """GET /api/bookings/?role=pro|client puis POST pour réserver."""

    serializer_class = BookingSerializer
    pagination_class = None

    def get_queryset(self):
        u = self.request.user
        qs = Booking.objects.select_related("service", "service__gym", "pro", "client", "partner")
        if self.request.query_params.get("role") == "pro":
            qs = qs.filter(pro=u)
        else:
            qs = qs.filter(Q(client=u) | Q(partner=u))
        when = self.request.query_params.get("when")
        if when == "past":
            qs = qs.filter(starts_at__lt=timezone.now()).order_by("-starts_at")
        elif when == "upcoming":
            qs = qs.filter(starts_at__gte=timezone.now()).exclude(status__in=["cancelled", "declined"])
        return qs

    def post(self, request):
        ser = BookingCreateSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        service = d["service"]
        client_part, _ = slots.split_price(service.price, bool(d.get("partner")))
        with transaction.atomic():
            # Revérification dans la transaction : deux personnes ne prennent pas le même créneau.
            if slots.overlaps(d["pro"], d["starts_at"], d["ends_at"]):
                return Response({"starts_at": ["Ce créneau vient d'être pris. Choisis-en un autre."]}, status=status.HTTP_400_BAD_REQUEST)
            booking = Booking.objects.create(
                service=service, pro=d["pro"], client=request.user, partner=d.get("partner"),
                starts_at=d["starts_at"], ends_at=d["ends_at"], mode=d["mode"],
                payment_method=d["payment_method"], price_total=service.price, price_client=client_part,
                note=d.get("note", ""),
            )
            get_or_create_conversation(request.user, d["pro"])
        return Response(BookingSerializer(booking, context={"request": request}).data, status=status.HTTP_201_CREATED)


class BookingActionView(APIView):
    """POST /api/bookings/<id>/<action>/ : confirm, decline, complete, mark_paid (pro) ; cancel (client ou pro)."""

    def post(self, request, pk, action):
        booking = get_object_or_404(Booking.objects.select_related("service", "pro", "client", "partner"), pk=pk)
        u = request.user
        if u.pk not in (booking.pro_id, booking.client_id):
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        handler = getattr(self, f"do_{action}", None)
        if handler is None:
            return Response({"detail": "Action inconnue."}, status=status.HTTP_404_NOT_FOUND)
        error = handler(u, booking)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        return Response(BookingSerializer(booking, context={"request": request}).data)

    @staticmethod
    def _pro_only(u, b):
        return None if u.pk == b.pro_id else "Seul le professionnel peut faire cela."

    def do_confirm(self, u, b):
        err = self._pro_only(u, b)
        if err or b.status != Booking.Status.PENDING:
            return err or "Cette réservation a déjà reçu une réponse."
        if slots.overlaps(b.pro, b.starts_at, b.ends_at, exclude_id=b.pk):
            return "Un autre rendez-vous occupe déjà ce créneau."
        b.status = Booking.Status.CONFIRMED
        b.save(update_fields=["status"])

    def do_decline(self, u, b):
        err = self._pro_only(u, b)
        if err or b.status != Booking.Status.PENDING:
            return err or "Cette réservation a déjà reçu une réponse."
        b.status = Booking.Status.DECLINED
        b.save(update_fields=["status"])

    def do_cancel(self, u, b):
        if b.status not in Booking.BLOCKING:
            return "Cette réservation ne peut plus être annulée."
        b.status = Booking.Status.CANCELLED
        b.save(update_fields=["status"])
        # Si la réservation était payée en ligne : le pro qui annule rembourse toujours, le client seulement s'il annule assez tôt.
        from apps.payments.services import client_refund_applies, flag_refunds

        flag_refunds("booking", b.pk, refund=u.pk == b.pro_id or client_refund_applies(b.starts_at))

    def do_complete(self, u, b):
        err = self._pro_only(u, b)
        if err:
            return err
        if b.status != Booking.Status.CONFIRMED or b.starts_at > timezone.now():
            return "Tu peux terminer une séance confirmée une fois l'heure passée."
        b.status = Booking.Status.DONE
        b.save(update_fields=["status"])

    def do_mark_paid(self, u, b):
        err = self._pro_only(u, b)
        if err:
            return err
        if b.status in (Booking.Status.DECLINED, Booking.Status.CANCELLED):
            return "Cette réservation est annulée."
        b.payment_status = Booking.Payment.PAID
        b.save(update_fields=["payment_status"])
