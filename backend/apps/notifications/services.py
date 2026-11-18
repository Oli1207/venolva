import logging

from .models import Notification

log = logging.getLogger(__name__)


def notify(user, kind: str, title: str, body: str = "", link: str = "") -> Notification | None:
    """Crée une notification. Ne doit jamais faire échouer l'action qui l'a déclenchée."""
    if user is None or not getattr(user, "is_active", False):
        return None
    try:
        return Notification.objects.create(user=user, kind=kind[:30], title=title[:120], body=body[:240], link=link[:120])
    except Exception:  # noqa: BLE001 : une notification perdue vaut mieux qu'une réservation annulée
        log.exception("Notification non créée (%s)", kind)
        return None
