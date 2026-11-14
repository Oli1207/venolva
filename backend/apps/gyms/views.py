from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Message
from apps.chat.services import get_or_create_conversation

from .models import ClassBooking, Gym, GymClass, GymHours, GymPlan, GymReview, MembershipRequest
from .serializers import (
    ClassSerializer, GymSerializer, HoursSerializer, PlanSerializer, RequestSerializer, ReviewSerializer,
)


def annotated_gyms():
    return Gym.objects.annotate(
        members_count=Count("members", filter=Q(members__visible=True), distinct=True),
        rating_avg=Avg("reviews__rating"),
        reviews_count=Count("reviews", distinct=True),
    )


class GymListView(ListAPIView):
    """Salles filtrables par commune et par nom : GET /api/gyms/?commune=Cocody&q=riviera"""

    serializer_class = GymSerializer
    pagination_class = None

    def get_queryset(self):
        qs = annotated_gyms()
        commune = self.request.query_params.get("commune")
        q = self.request.query_params.get("q")
        if commune:
            qs = qs.filter(commune__iexact=commune)
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(commune__icontains=q))
        return qs.order_by("-members_count", "name")[:50]


def gym_payload(gym: Gym, request) -> dict:
    """Profil public complet d'une salle."""
    stats = annotated_gyms().get(pk=gym.pk)
    today = gym.hours_today()
    classes = (
        gym.classes.filter(active=True, starts_at__gte=timezone.now())
        .annotate(booked_count=Count("bookings"))
        .order_by("starts_at")[:20]
    )
    mine = GymReview.objects.filter(gym=gym, user=request.user).first()
    return {
        "id": gym.id,
        "name": gym.name,
        "commune": gym.commune,
        "address": gym.address,
        "description": gym.description,
        "equipment": gym.equipment,
        "verified": gym.verified,
        "owner_id": gym.owner_id,
        "is_owner": gym.owner_id == request.user.pk,
        "hours": HoursSerializer(gym.hours.all(), many=True).data,
        "open_now": gym.is_open_now(),
        "today": {"opens": today.opens.strftime("%H:%M"), "closes": today.closes.strftime("%H:%M")} if today else None,
        "rating_avg": round(stats.rating_avg, 1) if stats.rating_avg else None,
        "reviews_count": stats.reviews_count,
        "members_count": stats.members_count,
        "plans": PlanSerializer(gym.plans.filter(active=True), many=True).data,
        "classes": ClassSerializer(classes, many=True, context={"request": request}).data,
        "my_review": ReviewSerializer(mine).data if mine else None,
    }


class GymDetailView(APIView):
    def get(self, request, pk):
        return Response(gym_payload(get_object_or_404(Gym, pk=pk), request))


class GymReviewsView(APIView):
    """GET /api/gyms/<id>/reviews/ puis POST {rating, comment} : un avis par membre, modifiable."""

    def get(self, request, pk):
        gym = get_object_or_404(Gym, pk=pk)
        return Response(ReviewSerializer(gym.reviews.select_related("user")[:30], many=True).data)

    def post(self, request, pk):
        gym = get_object_or_404(Gym, pk=pk)
        if gym.owner_id == request.user.pk:
            return Response({"detail": "Tu ne peux pas noter ta propre salle."}, status=status.HTTP_400_BAD_REQUEST)
        ser = ReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        review, _ = GymReview.objects.update_or_create(
            gym=gym, user=request.user, defaults={"rating": ser.validated_data["rating"], "comment": ser.validated_data.get("comment", "").strip()}
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class PlanRequestView(APIView):
    """POST /api/gym-plans/<id>/request/ : demander une formule. La salle est prévenue par message."""

    def post(self, request, pk):
        plan = get_object_or_404(GymPlan.objects.select_related("gym", "gym__owner"), pk=pk, active=True)
        gym = plan.gym
        if gym.owner_id == request.user.pk:
            return Response({"detail": "C'est ta propre salle."}, status=status.HTTP_400_BAD_REQUEST)
        if MembershipRequest.objects.filter(plan=plan, user=request.user, status="pending").exists():
            return Response({"detail": "Ta demande est déjà en attente."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            req = MembershipRequest.objects.create(plan=plan, user=request.user)
            if gym.owner_id:
                conv = get_or_create_conversation(request.user, gym.owner)
                price = f"{plan.price:,}".replace(",", " ")
                Message.objects.create(
                    conversation=conv, sender=request.user,
                    body=f"Bonjour, je souhaite la formule « {plan.name} » ({price} F) à {gym.name}.",
                )
                conv.save(update_fields=["updated_at"])
        return Response(RequestSerializer(req).data, status=status.HTTP_201_CREATED)


class MyRequestsView(APIView):
    """GET /api/gym-requests/ : mes demandes de formule."""

    def get(self, request):
        qs = MembershipRequest.objects.filter(user=request.user).select_related("plan", "plan__gym", "user")
        return Response(RequestSerializer(qs, many=True).data)


class MyRequestCancelView(APIView):
    def post(self, request, pk):
        req = get_object_or_404(MembershipRequest, pk=pk, user=request.user)
        if req.status != MembershipRequest.Status.PENDING:
            return Response({"detail": "Cette demande a déjà reçu une réponse."}, status=status.HTTP_400_BAD_REQUEST)
        req.status = MembershipRequest.Status.CANCELLED
        req.save(update_fields=["status"])
        return Response(RequestSerializer(req).data)


class ClassBookView(APIView):
    """POST /api/gym-classes/<id>/book/ réserve une place ; .../cancel/ la libère."""

    def post(self, request, pk, action):
        if action not in ("book", "cancel"):
            return Response({"detail": "Action inconnue."}, status=status.HTTP_404_NOT_FOUND)
        cls = get_object_or_404(GymClass, pk=pk, active=True)
        if cls.starts_at <= timezone.now():
            return Response({"detail": "Ce cours a déjà commencé."}, status=status.HTTP_400_BAD_REQUEST)
        if action == "cancel":
            seat = ClassBooking.objects.filter(gym_class=cls, user=request.user).first()
            if seat is None:
                return Response({"detail": "Tu n'as pas de place pour ce cours."}, status=status.HTTP_400_BAD_REQUEST)
            from apps.payments.services import client_refund_applies, flag_refunds

            flag_refunds("class", seat.pk, refund=client_refund_applies(cls.starts_at))
            seat.delete()
        else:
            try:
                with transaction.atomic():
                    if cls.bookings.count() >= cls.capacity:
                        return Response({"detail": "Ce cours est complet."}, status=status.HTTP_400_BAD_REQUEST)
                    ClassBooking.objects.create(gym_class=cls, user=request.user)
            except IntegrityError:
                return Response({"detail": "Tu as déjà une place pour ce cours."}, status=status.HTTP_400_BAD_REQUEST)
        cls = GymClass.objects.annotate(booked_count=Count("bookings")).get(pk=cls.pk)
        return Response(ClassSerializer(cls, context={"request": request}).data)


# --- Espace du gérant -------------------------------------------------------------------------------------------


class IsGymManager(BasePermission):
    message = "Réservé aux gérants de salle vérifiés."

    def has_permission(self, request, view):
        u = request.user
        if not u.is_authenticated:
            return False
        return u.owned_gyms.exists() or bool(u.pro_type == "gym" and u.pro_verified)


def my_gym(user):
    return user.owned_gyms.first()


class MyGymView(APIView):
    """GET : ma salle. POST : la créer (une seule). PATCH : modifier ses informations."""

    permission_classes = [IsGymManager]
    FIELDS = ("name", "commune", "address", "description", "equipment")

    def _clean(self, data):
        out = {}
        for k in self.FIELDS:
            if k in data:
                out[k] = data[k]
        if "equipment" in out:
            eq = out["equipment"]
            if not isinstance(eq, list) or len(eq) > 12 or any(not isinstance(e, str) or not 1 <= len(e) <= 30 for e in eq):
                raise ValidationError({"equipment": ["12 équipements au maximum, de 30 caractères."]})
        for k, limit in (("name", 120), ("commune", 60), ("address", 200), ("description", 500)):
            if k in out and (not isinstance(out[k], str) or len(out[k]) > limit):
                raise ValidationError({k: [f"{limit} caractères au maximum."]})
        return out

    def get(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response({"detail": "Tu n'as pas encore de salle."}, status=status.HTTP_404_NOT_FOUND)
        return Response(gym_payload(gym, request))

    def post(self, request):
        if my_gym(request.user):
            return Response({"detail": "Tu as déjà une salle."}, status=status.HTTP_400_BAD_REQUEST)
        data = self._clean(request.data)
        if not data.get("name", "").strip() or not data.get("commune", "").strip():
            return Response({"detail": "Le nom et la commune sont obligatoires."}, status=status.HTTP_400_BAD_REQUEST)
        gym = Gym.objects.create(owner=request.user, verified=request.user.pro_verified, **data)
        return Response(gym_payload(gym, request), status=status.HTTP_201_CREATED)

    def patch(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response({"detail": "Tu n'as pas encore de salle."}, status=status.HTTP_404_NOT_FOUND)
        data = self._clean(request.data)
        for k, v in data.items():
            setattr(gym, k, v)
        gym.save()
        return Response(gym_payload(gym, request))


class MyHoursView(APIView):
    """PUT /api/my/gym/hours/ : remplace les horaires de la semaine (une plage par jour)."""

    permission_classes = [IsGymManager]

    def put(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response({"detail": "Tu n'as pas encore de salle."}, status=status.HTTP_404_NOT_FOUND)
        ser = HoursSerializer(data=request.data, many=True)
        ser.is_valid(raise_exception=True)
        days = [r["weekday"] for r in ser.validated_data]
        if len(days) != len(set(days)):
            return Response({"detail": "Une seule plage par jour."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            gym.hours.all().delete()
            GymHours.objects.bulk_create([GymHours(gym=gym, **r) for r in ser.validated_data])
        return Response(HoursSerializer(gym.hours.all(), many=True).data)


class MyPlansView(APIView):
    permission_classes = [IsGymManager]

    def get(self, request):
        gym = my_gym(request.user)
        return Response(PlanSerializer(gym.plans.all() if gym else [], many=True).data)

    def post(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response({"detail": "Crée d'abord ta salle."}, status=status.HTTP_400_BAD_REQUEST)
        ser = PlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(PlanSerializer(ser.save(gym=gym)).data, status=status.HTTP_201_CREATED)


class MyPlanDetailView(APIView):
    permission_classes = [IsGymManager]

    def _plan(self, request, pk):
        gym = my_gym(request.user)
        return get_object_or_404(GymPlan, pk=pk, gym=gym) if gym else get_object_or_404(GymPlan, pk=0)

    def patch(self, request, pk):
        plan = self._plan(request, pk)
        ser = PlanSerializer(plan, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        return Response(PlanSerializer(ser.save()).data)

    def delete(self, request, pk):
        plan = self._plan(request, pk)
        if plan.requests.exists():  # l'historique des demandes reste lisible
            plan.active = False
            plan.save(update_fields=["active"])
        else:
            plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyClassesView(APIView):
    permission_classes = [IsGymManager]

    def get(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response([])
        qs = gym.classes.filter(starts_at__gte=timezone.now() - timedelta(hours=6)).annotate(booked_count=Count("bookings"))
        return Response(ClassSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response({"detail": "Crée d'abord ta salle."}, status=status.HTTP_400_BAD_REQUEST)
        ser = ClassSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        return Response(ClassSerializer(ser.save(gym=gym), context={"request": request}).data, status=status.HTTP_201_CREATED)


class MyClassDetailView(APIView):
    permission_classes = [IsGymManager]

    def _cls(self, request, pk):
        gym = my_gym(request.user)
        return get_object_or_404(GymClass, pk=pk, gym=gym) if gym else get_object_or_404(GymClass, pk=0)

    def patch(self, request, pk):
        cls = self._cls(request, pk)
        ser = ClassSerializer(cls, data=request.data, partial=True, context={"request": request})
        ser.is_valid(raise_exception=True)
        if ser.validated_data.get("capacity", cls.capacity) < cls.bookings.count():
            return Response({"capacity": ["Il y a déjà plus de réservations que cela."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ClassSerializer(ser.save(), context={"request": request}).data)

    def delete(self, request, pk):
        cls = self._cls(request, pk)
        cls.active = False  # on garde la trace des réservations
        cls.save(update_fields=["active"])
        # Cours annulé par la salle : toutes les places payées en ligne sont à rembourser.
        from apps.payments.services import flag_refunds

        for seat_id in cls.bookings.values_list("pk", flat=True):
            flag_refunds("class", seat_id, refund=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyClassParticipantsView(APIView):
    permission_classes = [IsGymManager]

    def get(self, request, pk):
        gym = my_gym(request.user)
        cls = get_object_or_404(GymClass, pk=pk, gym=gym) if gym else get_object_or_404(GymClass, pk=0)
        return Response(
            [{"id": b.user_id, "display_name": b.user.display_name, "initials": b.user.initials} for b in cls.bookings.select_related("user")]
        )


class MyGymRequestsView(APIView):
    """GET /api/my/gym/requests/?status=pending puis POST .../<id>/accept|decline/."""

    permission_classes = [IsGymManager]

    def get(self, request):
        gym = my_gym(request.user)
        if not gym:
            return Response([])
        qs = MembershipRequest.objects.filter(plan__gym=gym).select_related("plan", "plan__gym", "user")
        if request.query_params.get("status") in dict(MembershipRequest.Status.choices):
            qs = qs.filter(status=request.query_params["status"])
        return Response(RequestSerializer(qs[:100], many=True).data)


class MyGymRequestActionView(APIView):
    permission_classes = [IsGymManager]

    def post(self, request, pk, action):
        if action not in ("accept", "decline"):
            return Response({"detail": "Action inconnue."}, status=status.HTTP_404_NOT_FOUND)
        gym = my_gym(request.user)
        req = get_object_or_404(MembershipRequest, pk=pk, plan__gym=gym) if gym else get_object_or_404(MembershipRequest, pk=0)
        if req.status != MembershipRequest.Status.PENDING:
            return Response({"detail": "Cette demande a déjà reçu une réponse."}, status=status.HTTP_400_BAD_REQUEST)
        req.status = MembershipRequest.Status.ACCEPTED if action == "accept" else MembershipRequest.Status.DECLINED
        req.save(update_fields=["status"])
        return Response(RequestSerializer(req).data)
