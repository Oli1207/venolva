from datetime import timedelta

from .models import Meetup

ON_TIME_MARGIN = timedelta(minutes=10)
MIN_DONE_FOR_SCORE = 3


def punctuality(user):
    """Note sur 5 : part des séances terminées où la personne est arrivée à l'heure (10 min de marge).

    Renvoie None tant qu'il y a moins de 3 séances terminées, pour ne pas juger sur trop peu."""
    done = list(
        Meetup.objects.filter(status=Meetup.Status.DONE).filter(organizer=user)
        | Meetup.objects.filter(status=Meetup.Status.DONE).filter(partner=user)
    )
    if len(done) < MIN_DONE_FOR_SCORE:
        return None
    on_time = 0
    for m in done:
        arrived = m.organizer_arrived_at if m.organizer_id == user.pk else m.partner_arrived_at
        if arrived and arrived <= m.starts_at + ON_TIME_MARGIN:
            on_time += 1
    return round(5 * on_time / len(done), 1)


def done_count(user) -> int:
    return (
        Meetup.objects.filter(status=Meetup.Status.DONE, organizer=user).count()
        + Meetup.objects.filter(status=Meetup.Status.DONE, partner=user).count()
    )
