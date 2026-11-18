"""Les identifiants sont des UUID : ces aides lisent ceux qui viennent d'une requête sans planter."""
import uuid


def as_uuid(value):
    """Renvoie un UUID, ou None si la valeur n'en est pas un."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def uuid_list(values, limit=50):
    """Garde les UUID valides d'une liste (sans doublon, au plus `limit`)."""
    if not isinstance(values, list):
        return []
    out = []
    for v in values:
        u = as_uuid(v) if not isinstance(v, bool) else None
        if u is not None and u not in out:
            out.append(u)
    return out[:limit]
