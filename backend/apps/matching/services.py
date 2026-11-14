"""Calcul de compatibilité entre deux membres.

Total sur 100 : salle 35, objectif 25, jours 15, créneaux 15, niveau 10.
Les deux profils doivent être dans la même commune ou la même salle pour être comparés."""
from apps.accounts.models import Profile

W_GYM, W_GOALS, W_DAYS, W_PERIODS, W_LEVEL = 35, 25, 15, 15, 10
SAME_COMMUNE_BONUS = 10  # même commune mais pas la même salle


def _overlap(a: list, b: list) -> list:
    return sorted(set(a) & set(b))


def _ratio(shared: list, a: list, b: list) -> float:
    smallest = min(len(a), len(b))
    return len(shared) / smallest if smallest else 0.0


def compatibility(me: Profile, other: Profile) -> tuple[int, dict]:
    same_gym = bool(me.gym_id and me.gym_id == other.gym_id)
    same_commune = bool(me.user.commune and me.user.commune.lower() == other.user.commune.lower())
    goals = _overlap(me.goals, other.goals)
    days = _overlap(me.days, other.days)
    periods = _overlap(me.periods, other.periods)
    same_level = me.level == other.level

    score = 0.0
    score += W_GYM if same_gym else (SAME_COMMUNE_BONUS if same_commune else 0)
    score += W_GOALS * _ratio(goals, me.goals, other.goals)
    score += W_DAYS * _ratio(days, me.days, other.days)
    score += W_PERIODS * _ratio(periods, me.periods, other.periods)
    score += W_LEVEL if same_level else 0
    reasons = {
        "gym": same_gym,
        "commune": same_commune,
        "goals": goals,
        "days": days,
        "periods": periods,
        "level": same_level,
    }
    return round(score), reasons
