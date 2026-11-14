"""Aides communes aux tests."""
from rest_framework.test import APIClient

from apps.gyms.models import Gym

from .models import Profile, User

_counter = {"n": 0}


def make_gym(name="Salle Riviera 3", commune="Cocody"):
    return Gym.objects.create(name=name, commune=commune)


def make_member(name="Awa K.", commune="Cocody", gym=None, **profile):
    """Crée un membre complet (compte + profil terminé)."""
    _counter["n"] += 1
    user = User.objects.create_user(phone=f"07{_counter['n']:08d}", display_name=name, commune=commune)
    defaults = dict(
        goals=["weight_loss"], level="debutant", gym=gym, days=[0, 2, 4], periods=["evening"], onboarded=True
    )
    defaults.update(profile)
    Profile.objects.create(user=user, **defaults)
    return user


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c
