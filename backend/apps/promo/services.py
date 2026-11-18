"""Demandes, attribution et affichage des mises à la une."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.backoffice.config import cfg
from apps.feed.models import Post
from apps.gyms.models import Gym
from apps.market.models import Listing
from apps.notifications.services import notify

from .models import Feature, FeatureEvent

TARGET_MODEL = {"post": Post, "gym": Gym, "listing": Listing}


class PromoError(Exception):
    pass


def resolve_target(kind: str, target_id):
    """Renvoie l'objet à mettre en avant ou lève PromoError."""
    from apps.accounts.models import User

    model = User if kind == "pro" else TARGET_MODEL.get(kind)
    if model is None:
        raise PromoError("Type de contenu inconnu.")
    obj = model.objects.filter(pk=target_id).first()
    if obj is None:
        raise PromoError("Contenu introuvable.")
    return obj


def owner_of(kind: str, obj):
    return {"post": lambda: obj.author, "pro": lambda: obj, "gym": lambda: obj.owner, "listing": lambda: obj.seller}[kind]()


def validate_target(kind: str, obj):
    """Ce qui peut être mis à la une : un pro validé, une annonce en vente, une salle."""
    if kind == "pro" and not (obj.pro_type and obj.pro_verified):
        raise PromoError("Seuls les professionnels validés peuvent être mis à la une.")
    if kind == "listing" and obj.status != "active":
        raise PromoError("Seule une annonce en vente peut être mise à la une.")


def _fields(kind: str, obj) -> dict:
    return {kind: obj}


def _window_overlap(starts, ends):
    return Q(status="approved", starts_at__lt=ends, ends_at__gt=starts)


def request_feature(user, kind: str, target_id, days: int, commune: str = "") -> Feature:
    s = cfg()
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= s.featured_max_days:
        raise PromoError(f"La durée doit être de 1 à {s.featured_max_days} jours.")
    obj = resolve_target(kind, target_id)
    owner = owner_of(kind, obj)
    if owner is None or owner.pk != user.pk:
        raise PromoError("Tu ne peux mettre à la une que tes propres contenus.")
    validate_target(kind, obj)
    if Feature.objects.filter(**_fields(kind, obj), status__in=["pending", "approved"], ends_at__isnull=True).exists() or Feature.objects.filter(
        **_fields(kind, obj), status="approved", ends_at__gt=timezone.now()
    ).exists():
        raise PromoError("Ce contenu est déjà en cours de demande ou à la une.")
    return Feature.objects.create(kind=kind, **_fields(kind, obj), requested_days=days, scope_commune=commune[:60], requested_by=user)


def create_direct(actor, kind: str, target_id, days: int, commune: str = "", sponsored: bool = False, note: str = "") -> Feature:
    """L'équipe met un contenu à la une sans passer par une demande."""
    obj = resolve_target(kind, target_id)
    validate_target(kind, obj)
    f = Feature.objects.create(kind=kind, **_fields(kind, obj), requested_days=days, scope_commune=commune[:60], requested_by=actor, sponsored=sponsored, note=note[:200])
    return approve(f, actor, days=days)


def approve(feature: Feature, actor, days: int | None = None) -> Feature:
    s = cfg()
    if feature.status not in ("pending",):
        raise PromoError("Cette demande a déjà reçu une réponse.")
    days = days or feature.requested_days
    if not 1 <= days <= s.featured_max_days:
        raise PromoError(f"La durée doit être de 1 à {s.featured_max_days} jours.")
    start = timezone.now()
    end = start + timedelta(days=days)
    with transaction.atomic():
        taken = Feature.objects.filter(_window_overlap(start, end)).exclude(pk=feature.pk).count()
        if taken >= s.featured_slots:
            raise PromoError(f"Les {s.featured_slots} places sont déjà prises sur cette période.")
        feature.status, feature.starts_at, feature.ends_at, feature.decided_by = Feature.Status.APPROVED, start, end, actor
        feature.save(update_fields=["status", "starts_at", "ends_at", "decided_by"])
    if feature.requested_by_id and feature.requested_by_id != getattr(actor, "pk", None):
        notify(feature.requested_by, "feature_approved", "Ta mise à la une est accordée", f"Pendant {days} jour{'s' if days > 1 else ''}.", "/a-la-une")
    return feature


def reject(feature: Feature, actor, note: str = "") -> Feature:
    if feature.status != "pending":
        raise PromoError("Cette demande a déjà reçu une réponse.")
    feature.status, feature.decided_by, feature.note = Feature.Status.REJECTED, actor, note[:200]
    feature.save(update_fields=["status", "decided_by", "note"])
    notify(feature.requested_by, "feature_rejected", "Mise à la une refusée", note[:200], "/a-la-une")
    return feature


def end_now(feature: Feature, actor) -> Feature:
    if feature.status != "approved":
        raise PromoError("Cette mise à la une n'est pas en cours.")
    feature.status, feature.ends_at, feature.decided_by = Feature.Status.CANCELLED, timezone.now(), actor
    feature.save(update_fields=["status", "ends_at", "decided_by"])
    return feature


def live_qs(commune: str = ""):
    now = timezone.now()
    qs = Feature.objects.filter(status="approved", starts_at__lte=now, ends_at__gt=now)
    if commune:
        qs = qs.filter(Q(scope_commune="") | Q(scope_commune__iexact=commune))
    else:
        qs = qs.filter(scope_commune="")
    return qs


def featured_ids(kind: str, commune: str = "") -> set[int]:
    """Identifiants à faire passer en premier dans une liste (annuaire des pros, des salles, marché)."""
    field = f"{kind}_id"
    return set(live_qs(commune).filter(kind=kind).values_list(field, flat=True))


def payload(f: Feature) -> dict | None:
    """Ce que l'app affiche dans le bandeau « À la une ». None si le contenu a disparu ou n'est plus montrable."""
    t = f.target
    if t is None:
        return None
    base = {"id": f.id, "kind": f.kind, "label": "Sponsorisé" if f.sponsored else "À la une", "image": None}
    if f.kind == "post":
        title = t.title or t.body.split("\n")[0][:90]
        return {**base, "title": title, "subtitle": t.author.display_name, "link": f"/publication/{t.id}"}
    if f.kind == "pro":
        spec = getattr(getattr(t, "pro_profile", None), "speciality", "") or ""
        return {**base, "title": t.display_name, "subtitle": spec or t.get_pro_type_display(), "link": f"/pros/{t.id}"}
    if f.kind == "gym":
        return {**base, "title": t.name, "subtitle": t.commune, "link": f"/salles/{t.id}"}
    if t.status != "active":
        return None
    photo = t.photos.first()
    price = f"{t.price:,}".replace(",", " ")
    return {**base, "title": t.title, "subtitle": f"{price} F", "link": f"/marche/{t.id}", "image": photo.image.url if photo else None}


def record(feature_id: int, user, kind: str) -> None:
    """Compte une vue ou un clic, une fois par membre et par jour."""
    if kind not in ("view", "click"):
        return
    try:
        with transaction.atomic():
            FeatureEvent.objects.create(feature_id=feature_id, user=user, kind=kind, day=timezone.localdate())
            Feature.objects.filter(pk=feature_id, status="approved").update(**{"views" if kind == "view" else "clicks": F("views" if kind == "view" else "clicks") + 1})
    except IntegrityError:
        pass  # déjà compté aujourd'hui
