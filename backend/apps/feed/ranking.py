"""Le fil d'actualité : choisir, classer et espacer ce qu'on montre à chaque membre.

Chaîne en quatre temps, chacun testable seul :
  1. candidats   : un lot borné de publications récentes, sans les masquées ni celles des membres bloqués ;
  2. score       : `score_post` (fonction pure) combine fraîcheur, proximité, pro validé, engagement, affinité et
                   « déjà vu » ; elle renvoie aussi les raisons, pour comprendre pourquoi une publication est là ;
  3. diversité   : au plus N publications d'un même auteur par page ;
  4. mises en avant : les contenus « À la une » / sponsorisés sont insérés à intervalle régulier, en rotation
                   équitable (les moins vus d'abord), jamais avec un auteur bloqué, jamais ceux déjà cliqués aujourd'hui.

La pagination est un curseur `as_of:offset` : l'ordre reste stable d'une page à l'autre pendant la lecture.
Les poids que l'équipe règle vivent dans PlatformSettings ; les constantes ci-dessous sont les réglages fins.
"""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_tz

from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import Profile
from apps.backoffice.config import cfg
from apps.chat.models import Conversation
from apps.promo import services as promo
from apps.promo.models import FeatureEvent
from apps.safety.services import blocked_ids

from .models import Post, PostImpression, PostLike

PAGE_SIZE = 12
MAX_PAGE_SIZE = 30
CANDIDATES = 300
POST_WINDOW = timedelta(days=14)
ARTICLE_WINDOW = timedelta(days=60)  # un article reste utile plus longtemps qu'une publication
SEEN_DECAY = 0.55  # chaque fois qu'on a vu une publication, elle compte ce coefficient de moins
LIKE_SATURATION = 20  # au-delà, des likes de plus n'ajoutent presque rien
URGENT_HOURS = 48


@dataclass
class Signals:
    """Tout ce qu'il faut savoir sur une publication pour la noter. Pas de requête ici."""

    age_hours: float
    likes: int = 0
    seen: int = 0
    is_pro: bool = False
    is_article: bool = False
    same_commune: bool = False
    same_gym: bool = False
    shared_goal: bool = False
    affinity: bool = False  # on se connaît déjà : discussion ou séance en commun
    is_mine: bool = False
    hours_to_start: float | None = None  # demande de binôme : dans combien d'heures


@dataclass
class Weights:
    half_life_hours: float = 36
    pro_boost: float = 0.20
    local_boost: float = 0.40
    engagement: float = 0.5
    affinity: float = 0.3
    urgent: float = 0.4

    @classmethod
    def from_settings(cls, s=None):
        s = s or cfg()
        return cls(half_life_hours=s.feed_half_life_hours, pro_boost=s.feed_pro_boost_pct / 100, local_boost=s.feed_local_boost_pct / 100)


def score_post(sig: Signals, w: Weights) -> tuple[float, list[str]]:
    """Note d'une publication pour un lecteur. Plus c'est haut, plus c'est haut dans le fil."""
    half_life = w.half_life_hours * (2.0 if sig.is_article else 1.0)
    fresh = 0.5 ** (max(sig.age_hours, 0) / max(half_life, 0.1))
    reasons = [f"fraîcheur {fresh:.2f}"]
    bonus = 1.0

    relevance = (0.5 if sig.same_commune else 0) + (0.3 if sig.same_gym else 0) + (0.2 if sig.shared_goal else 0)
    if relevance:
        bonus += w.local_boost * relevance
        reasons.append("proche de toi")
    if sig.is_pro:
        bonus += w.pro_boost
        reasons.append("pro validé")
    if sig.likes:
        eng = min(math.log1p(sig.likes) / math.log1p(LIKE_SATURATION), 1.0)
        bonus += w.engagement * eng
        reasons.append(f"{sig.likes} j'aime")
    if sig.affinity:
        bonus += w.affinity
        reasons.append("tu le connais")
    if sig.hours_to_start is not None and 0 < sig.hours_to_start <= URGENT_HOURS:
        # une séance qui approche est plus utile qu'une plus lointaine : elle prend le dessus sur la fraîcheur
        bonus += w.urgent * (1 - sig.hours_to_start / URGENT_HOURS)
        reasons.append("séance proche")

    score = fresh * bonus
    if sig.seen and not sig.is_mine:
        score *= SEEN_DECAY ** sig.seen
        reasons.append(f"déjà vu {sig.seen}×")
    return score, reasons


def diversify(ranked: list, per_author: int, key=lambda r: r["author_id"]) -> list:
    """Garde l'ordre mais repousse en fin de liste les publications en trop d'un même auteur sur une même page."""
    kept, pushed, counts = [], [], {}
    for item in ranked:
        a = key(item)
        window = len(kept) // PAGE_SIZE
        slot = (a, window)
        if counts.get(slot, 0) >= per_author:
            pushed.append(item)
            continue
        counts[slot] = counts.get(slot, 0) + 1
        kept.append(item)
    return kept + pushed


def insert_boosts(items: list, boosts: list, every: int) -> list:
    """Place un contenu mis en avant toutes les `every` positions (le premier après `every - 1` publications)."""
    if not every or not boosts:
        return list(items)
    out = list(items)
    for i, b in enumerate(boosts):
        pos = (every - 1) + i * every
        if pos > len(out):
            break  # pas assez de publications : on n'empile pas les pubs en fin de fil
        out.insert(pos, b)
    return out


def rotate_boosts(features: list, user_id: int, day) -> list:
    """Rotation équitable : les moins vus d'abord, puis un ordre stable par membre et par jour."""
    return sorted(features, key=lambda f: (f.views, (f.id * 2654435761 + user_id * 40503 + day.toordinal()) % 9973))


# ------------------------------------------------------------------ assemblage

def _context(user):
    prof = Profile.objects.filter(user=user).only("gym_id", "goals").first()
    friends = set(
        Conversation.objects.filter(Q(user_a=user) | Q(user_b=user)).values_list("user_a_id", "user_b_id")
        .distinct()
    )
    known = {i for pair in friends for i in pair} - {user.pk}
    return {
        "commune": (user.commune or "").lower(),
        "gym_id": getattr(prof, "gym_id", None),
        "goals": set(getattr(prof, "goals", []) or []),
        "known": known,
    }


def candidates(user, as_of):
    hidden = blocked_ids(user)
    recent = Q(kind__in=["text", "buddy"], created_at__gte=as_of - POST_WINDOW) | Q(kind="article", created_at__gte=as_of - ARTICLE_WINDOW)
    qs = (
        Post.objects.filter(recent, hidden=False, created_at__lte=as_of)
        .exclude(author_id__in=hidden)
        .exclude(kind="buddy", starts_at__lte=as_of)  # une séance passée ne sert plus à personne
        .select_related("author", "author__profile", "gym")
        .annotate(n_likes=Count("likes"))
        .order_by("-created_at")[:CANDIDATES]
    )
    return list(qs)


def rank(user, as_of=None, kind=None, pros_only=False):
    """Toutes les publications classées pour ce membre, avec note et raisons."""
    as_of = as_of or timezone.now()
    w = Weights.from_settings()
    ctx = _context(user)
    posts = candidates(user, as_of)
    if kind:
        posts = [p for p in posts if p.kind == kind]
    if pros_only:
        posts = [p for p in posts if p.author.pro_type and p.author.pro_verified]
    seen = dict(PostImpression.objects.filter(user=user, post__in=posts, last_seen_at__lte=as_of).values_list("post_id", "seen"))
    out = []
    for p in posts:
        a = p.author
        prof = getattr(a, "profile", None)
        sig = Signals(
            age_hours=(as_of - p.created_at).total_seconds() / 3600,
            likes=p.n_likes,
            seen=seen.get(p.pk, 0),
            is_pro=bool(a.pro_type and a.pro_verified),
            is_article=p.kind == Post.Kind.ARTICLE,
            same_commune=bool(ctx["commune"] and (a.commune or "").lower() == ctx["commune"]),
            same_gym=bool(ctx["gym_id"] and (p.gym_id == ctx["gym_id"] or getattr(prof, "gym_id", None) == ctx["gym_id"])),
            shared_goal=bool(ctx["goals"] & set(getattr(prof, "goals", []) or [])),
            affinity=a.pk in ctx["known"],
            is_mine=a.pk == user.pk,
            hours_to_start=(p.starts_at - as_of).total_seconds() / 3600 if p.starts_at else None,
        )
        score, reasons = score_post(sig, w)
        out.append({"post": p, "score": score, "reasons": reasons, "author_id": a.pk})
    out.sort(key=lambda r: (-r["score"], -r["post"].pk))
    return diversify(out, cfg().feed_max_per_author)


def boost_items(user, as_of, excluded_posts: set[int]):
    """Les mises en avant à insérer : en cours, pas déjà cliquées aujourd'hui, jamais d'un auteur bloqué."""
    hidden = blocked_ids(user)
    day = timezone.localdate()
    clicked = set(FeatureEvent.objects.filter(user=user, kind="click", day=day).values_list("feature_id", flat=True))
    feats = []
    for f in promo.live_qs(user.commune or "").select_related("post", "pro", "gym", "listing"):
        if f.pk in clicked:
            continue
        t = f.target
        if t is None:
            continue
        owner = promo.owner_of(f.kind, t)
        if owner is not None and owner.pk in hidden:
            continue
        if f.kind == "post" and (t.hidden or t.pk in excluded_posts):
            continue
        feats.append(f)
    limit = cfg().featured_slots
    return rotate_boosts(feats, user.pk, day)[:limit]


def build_page(user, cursor: str = "", size: int = PAGE_SIZE, kind=None, pros_only=False):
    """Renvoie (éléments de la page, curseur suivant ou None). Les éléments sont {type, post|feature, ...}."""
    size = max(1, min(size, MAX_PAGE_SIZE))
    now = timezone.now()
    as_of, offset = now, 0
    if cursor:
        try:
            ts, off = cursor.split(":")
            as_of = max(now - timedelta(hours=6), datetime.fromtimestamp(int(ts), tz=dt_tz.utc))  # un curseur n'a pas à vivre plus de 6 h
            offset = max(int(off), 0)
        except (ValueError, OverflowError, OSError):
            pass
    organic = rank(user, as_of, kind, pros_only)
    sponsored = [] if (kind or pros_only) else boost_items(user, as_of, set())
    featured_post_ids = {f.post_id for f in sponsored if f.kind == "post"}
    organic = [r for r in organic if r["post"].pk not in featured_post_ids]
    boosts = [{"type": "feature", "feature": f} for f in sponsored]
    rows = [{"type": "post", **r} for r in organic]
    merged = insert_boosts(rows, boosts, cfg().feed_boost_every)
    page = merged[offset: offset + size]
    nxt = f"{int(as_of.timestamp())}:{offset + size}" if offset + size < len(merged) else None
    return page, nxt


def record_seen(user, post_ids) -> int:
    """Note que le membre a vu ces publications (au plus 50 d'un coup, une fois chacune)."""
    ids = {int(i) for i in post_ids if str(i).isdigit()}
    ids = set(list(ids)[:50])
    ids = set(Post.objects.filter(pk__in=ids).exclude(author=user).values_list("pk", flat=True))
    known = set(PostImpression.objects.filter(user=user, post_id__in=ids).values_list("post_id", flat=True))
    PostImpression.objects.bulk_create([PostImpression(user=user, post_id=i) for i in ids - known], ignore_conflicts=True)
    for imp in PostImpression.objects.filter(user=user, post_id__in=known):
        imp.seen += 1
        imp.save(update_fields=["seen", "last_seen_at"])
    return len(ids)
