"""Salles d'exemple pour le développement. Les vraies salles viennent du back-office ou de leurs gérants."""
from datetime import time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Profile, User
from apps.gyms.models import Gym, GymClass, GymHours, GymPlan

EXAMPLES = [
    ("Salle Riviera 3", "Cocody"),
    ("Iron Temple", "Marcory"),
    ("Palmeraie Athletic", "Cocody"),
    ("Yop Fitness", "Yopougon"),
    ("Plateau Gym", "Plateau"),
]


class Command(BaseCommand):
    help = "Crée quelques salles d'exemple, et un gérant avec horaires, formules et cours pour Salle Riviera 3 (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name, commune in EXAMPLES:
            _, new = Gym.objects.get_or_create(name=name, commune=commune)
            created += new

        gym = Gym.objects.get(name="Salle Riviera 3")
        boss, _ = User.objects.get_or_create(phone="+2250700000203", defaults=dict(display_name="Gérant Riviera", commune="Cocody"))
        boss.pro_type, boss.pro_verified = "gym", True
        boss.save()
        Profile.objects.get_or_create(user=boss, defaults=dict(onboarded=True))
        gym.owner, gym.verified = boss, True
        gym.address = "Riviera 3, Cocody"
        gym.description = "Salle de quartier : musculation, cardio et cours collectifs, ouverte tous les jours."
        gym.equipment = ["Musculation", "Cardio", "Cours collectifs", "Vestiaires", "Douches"]
        gym.save()

        gym.hours.all().delete()
        for wd in range(6):
            GymHours.objects.create(gym=gym, weekday=wd, opens=time(5), closes=time(22))
        GymHours.objects.create(gym=gym, weekday=6, opens=time(8), closes=time(20))

        for name, desc, price in [("Séance", "Accès pour la journée", 2000), ("Mensuel", "Accès illimité · 30 jours", 25000), ("Trimestriel", "Accès illimité · 3 mois", 65000)]:
            GymPlan.objects.update_or_create(gym=gym, name=name, defaults=dict(description=desc, price=price, active=True))

        if not gym.classes.filter(starts_at__gte=timezone.now()).exists():
            next_saturday = timezone.localtime() + timedelta(days=(5 - timezone.localtime().weekday()) % 7 or 7)
            GymClass.objects.create(gym=gym, name="Zumba et renfo", capacity=10, price=2000,
                                    starts_at=next_saturday.replace(hour=8, minute=0, second=0, microsecond=0))

        self.stdout.write(self.style.SUCCESS(f"{created} salle(s) créée(s). Gérant de démonstration : {boss.phone}"))
