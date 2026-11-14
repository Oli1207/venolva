"""Pros de démonstration pour le développement (comptes validés, services, disponibilités)."""
from datetime import time

from django.core.management.base import BaseCommand

from apps.accounts.models import Profile, User
from apps.gyms.models import Gym
from apps.pros.models import Availability, ProProfile, Service

DEMO = [
    dict(phone="+2250700000201", name="Coach Serge", commune="Marcory", type="coach", speciality="Préparation physique",
         bio="J'accompagne les débutants qui reprennent le sport : perte de poids, renforcement, bonnes bases.",
         credential="Brevet d'État (démo)", years=6, gym="Iron Temple",
         services=[("Séance d'essai", "trial", 60, 5000, False), ("Séance individuelle", "single", 60, 10000, False), ("Séance à deux", "duo", 60, 14000, True)]),
    dict(phone="+2250700000202", name="Fatou D.", commune="Plateau", type="nutrition", speciality="Nutrition et perte de poids",
         bio="Je t'aide à garder tes plats préférés en ajustant les portions.",
         credential="Diététicienne, n° d'ordre démo", years=4, gym=None,
         services=[("Première consultation", "consultation", 45, 15000, False), ("Suivi mensuel", "followup", 30, 40000, False)]),
]


class Command(BaseCommand):
    help = "Crée des professionnels de démonstration (idempotent)."

    def handle(self, *args, **options):
        for d in DEMO:
            user, _ = User.objects.get_or_create(phone=d["phone"], defaults=dict(display_name=d["name"], commune=d["commune"]))
            user.pro_type, user.pro_verified = d["type"], True
            user.save()
            Profile.objects.get_or_create(user=user, defaults=dict(onboarded=True))
            gym = Gym.objects.filter(name=d["gym"]).first() if d["gym"] else None
            ProProfile.objects.update_or_create(
                user=user,
                defaults=dict(speciality=d["speciality"], bio=d["bio"], credential=d["credential"], gym=gym,
                              years_experience=d["years"], status="approved"),
            )
            Availability.objects.filter(pro=user).delete()
            for wd in range(0, 6):  # lundi au samedi
                Availability.objects.create(pro=user, weekday=wd, start=time(8), end=time(12))
                Availability.objects.create(pro=user, weekday=wd, start=time(15), end=time(19))
            for name, kind, minutes, price, _duo in d["services"]:
                Service.objects.update_or_create(
                    owner=user, name=name,
                    defaults=dict(kind=kind, duration_min=minutes, price=price, modes=["gym", "online"] if d["type"] == "nutrition" else ["gym"], gym=gym, active=True),
                )
        self.stdout.write(self.style.SUCCESS(f"{len(DEMO)} pros de démonstration prêts."))
