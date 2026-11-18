"""Suppression de compte : on efface les données personnelles mais on garde les écritures comptables."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone


def blockers(user) -> list[str]:
    """Ce qui empêche de supprimer le compte maintenant. Liste vide = c'est possible."""
    from apps.gyms.models import Gym
    from apps.meetups.models import Meetup
    from apps.payments.models import Payment
    from apps.pros.models import Booking

    now = timezone.now()
    out = []
    if user.is_staff:
        out.append("Un compte de l'équipe se retire depuis l'administration.")
    live = Booking.objects.filter(Q(client=user) | Q(pro=user), status__in=["pending", "confirmed"], starts_at__gte=now)
    if live.exists():
        out.append("Tu as des réservations à venir : annule-les d'abord.")
    if Meetup.objects.filter(Q(organizer=user) | Q(partner=user), starts_at__gte=now).exclude(status__in=["cancelled", "done"]).exists():
        out.append("Tu as des séances à venir avec un binôme : annule-les d'abord.")
    if Payment.objects.filter(payee=user, status="paid", payout__isnull=True).exists():
        out.append("Il te reste de l'argent à recevoir : demande ton versement avant de partir.")
    if Gym.objects.filter(owner=user).exists():
        out.append("Tu gères une salle : transfère-la à l'équipe avant de supprimer ton compte.")
    return out


@transaction.atomic
def anonymize(user) -> None:
    """Le compte devient « Ancien membre », ne peut plus se connecter et disparaît des listes."""
    from apps.market.models import Listing
    from apps.notifications.models import Notification
    from apps.safety.models import Block

    from apps.feed.models import Post

    Post.objects.filter(author=user).delete()
    Listing.objects.filter(seller=user).delete()
    Notification.objects.filter(user=user).delete()
    Block.objects.filter(Q(blocker=user) | Q(blocked=user)).delete()
    profile = getattr(user, "profile", None)
    if profile is not None:
        profile.visible, profile.bio, profile.onboarded = False, "", False
        profile.save(update_fields=["visible", "bio", "onboarded"])
    user.email, user.phone = None, None
    user.display_name, user.commune = "Ancien membre", ""
    user.pro_type, user.pro_verified, user.is_active = "", False, False
    user.set_unusable_password()
    user.save()
