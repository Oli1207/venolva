from datetime import date

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Profile
from apps.meetups.services import done_count, punctuality
from apps.safety.services import blocked_ids
from config.ids import as_uuid

from .services import compatibility

DEFAULT_MIN_SCORE = 40
MAX_RESULTS = 30


def serialize_candidate(me: Profile, other: Profile) -> dict:
    score, reasons = compatibility(me, other)
    u = other.user
    return {
        "id": u.id,
        "display_name": u.display_name,
        "initials": u.initials,
        "commune": u.commune,
        "age": date.today().year - other.birth_year if other.birth_year else None,
        "gym": {"id": other.gym_id, "name": other.gym.name} if other.gym_id else None,
        "goals": other.goals,
        "level": other.level,
        "bio": other.bio,
        "score": score,
        "reasons": reasons,
        "punctuality": punctuality(u) if other.show_punctuality else None,
        "sessions_done": done_count(u),
    }


class MatchListView(APIView):
    """GET /api/matches/?min=40&gym=<id> : membres compatibles, du plus au moins compatible."""

    def get(self, request):
        me = request.user.profile
        try:
            minimum = int(request.query_params.get("min", DEFAULT_MIN_SCORE))
        except ValueError:
            minimum = DEFAULT_MIN_SCORE

        pool = Profile.objects.filter(visible=True, onboarded=True).exclude(user=request.user).exclude(user_id__in=blocked_ids(request.user)).select_related("user", "gym")
        near = Q(user__commune__iexact=request.user.commune) if request.user.commune else Q()
        if me.gym_id:
            near |= Q(gym_id=me.gym_id)
        pool = pool.filter(near)
        gym = as_uuid(request.query_params.get("gym"))
        if gym:
            pool = pool.filter(gym_id=gym)

        ranked = [serialize_candidate(me, p) for p in pool]
        ranked = [r for r in ranked if r["score"] >= minimum]
        ranked.sort(key=lambda r: r["score"], reverse=True)
        return Response(ranked[:MAX_RESULTS])


class MemberDetailView(APIView):
    """GET /api/members/<id>/ : profil d'un binôme, avec la compatibilité avec moi."""

    def get(self, request, pk):
        if pk in blocked_ids(request.user):
            return Response({"detail": "Introuvable."}, status=404)
        other = get_object_or_404(
            Profile.objects.select_related("user", "gym"), user_id=pk, visible=True, onboarded=True
        )
        return Response(serialize_candidate(request.user.profile, other))
