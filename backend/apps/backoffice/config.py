"""Accès aux réglages de la plateforme depuis le reste du code."""
from datetime import timedelta

from .models import CommissionOverride, PlatformSettings


def cfg() -> PlatformSettings:
    return PlatformSettings.load()


def lead_time() -> timedelta:
    return timedelta(hours=cfg().booking_lead_hours)


def commission_pct(payee, purpose: str) -> int:
    """Taux de commission appliqué à un paiement : celui du vendeur s'il en a un, sinon le taux par défaut."""
    if payee is not None:
        rows = {o.purpose: o.pct for o in CommissionOverride.objects.filter(user=payee, purpose__in=[purpose, "all"])}
        if purpose in rows:
            return rows[purpose]
        if "all" in rows:
            return rows["all"]
    s = cfg()
    return {"booking": s.commission_booking_pct, "class": s.commission_class_pct}.get(purpose, 0)
