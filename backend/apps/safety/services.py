from .models import Block


def blocked_ids(user) -> set[int]:
    """Les membres que je ne dois pas voir : ceux que j'ai bloqués et ceux qui m'ont bloqué."""
    if not getattr(user, "pk", None):
        return set()
    mine = Block.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    theirs = Block.objects.filter(blocked=user).values_list("blocker_id", flat=True)
    return set(mine) | set(theirs)


def is_blocked(a, b) -> bool:
    return b.pk in blocked_ids(a)
