"""Calcul des créneaux libres et des prix d'une réservation."""
from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.backoffice.config import lead_time

from .models import Availability, Booking

SLOT_STEP = timedelta(minutes=30)


def overlaps(pro, starts_at, ends_at, exclude_id=None) -> bool:
    qs = Booking.objects.filter(pro=pro, status__in=Booking.BLOCKING, starts_at__lt=ends_at, ends_at__gt=starts_at)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def inside_availability(pro, starts_at, ends_at) -> bool:
    local_start = timezone.localtime(starts_at)
    local_end = timezone.localtime(ends_at)
    if local_start.date() != local_end.date():
        return False
    return Availability.objects.filter(
        pro=pro, weekday=local_start.weekday(), start__lte=local_start.time(), end__gte=local_end.time()
    ).exists()


def free_slots(pro, service, day: date) -> list[datetime]:
    """Heures de début possibles ce jour-là, pour la durée du service."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    duration = timedelta(minutes=service.duration_min)
    booked = list(
        Booking.objects.filter(
            pro=pro, status__in=Booking.BLOCKING,
            starts_at__lt=timezone.make_aware(datetime.combine(day + timedelta(days=1), datetime.min.time()), tz),
            ends_at__gt=timezone.make_aware(datetime.combine(day, datetime.min.time()), tz),
        ).values_list("starts_at", "ends_at")
    )
    out = []
    for window in Availability.objects.filter(pro=pro, weekday=day.weekday()):
        cursor = timezone.make_aware(datetime.combine(day, window.start), tz)
        limit = timezone.make_aware(datetime.combine(day, window.end), tz)
        while cursor + duration <= limit:
            end = cursor + duration
            if cursor >= now + lead_time() and not any(s < end and e > cursor for s, e in booked):
                out.append(cursor)
            cursor += SLOT_STEP
    return sorted(set(out))


def split_price(total: int, with_partner: bool) -> tuple[int, int]:
    """(part du client, part du partenaire). Le client paie l'arrondi supérieur."""
    if not with_partner:
        return total, 0
    client = -(-total // 2)
    return client, total - client
