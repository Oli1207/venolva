from django.conf import settings
from django.db import models
from django.utils import timezone


class Gym(models.Model):
    name = models.CharField(max_length=120)
    commune = models.CharField(max_length=60, db_index=True)
    address = models.CharField(max_length=200, blank=True)
    description = models.CharField(max_length=500, blank=True)
    equipment = models.JSONField(default=list, blank=True)  # ex. ["Musculation", "Cardio", "Douches"]
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    verified = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_gyms"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.commune})"

    def hours_today(self):
        """Plage d'ouverture du jour (heure locale) ou None si fermé."""
        return self.hours.filter(weekday=timezone.localtime().weekday()).first()

    def is_open_now(self) -> bool:
        h = self.hours_today()
        return bool(h and h.opens <= timezone.localtime().time() < h.closes)


class GymHours(models.Model):
    """Une plage d'ouverture par jour. Pas de ligne pour un jour fermé."""

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="hours")
    weekday = models.PositiveSmallIntegerField()  # 0 = lundi
    opens = models.TimeField()
    closes = models.TimeField()

    class Meta:
        ordering = ["weekday"]
        constraints = [models.UniqueConstraint(fields=["gym", "weekday"], name="one_hours_row_per_day")]


class GymPlan(models.Model):
    """Une formule d'abonnement (séance, mensuel, trimestriel…)."""

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="plans")
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=120, blank=True)
    price = models.PositiveIntegerField(help_text="FCFA")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price", "id"]


class GymClass(models.Model):
    """Un cours collectif daté, avec un nombre de places."""

    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=80)
    starts_at = models.DateTimeField()
    duration_min = models.PositiveSmallIntegerField(default=60)
    capacity = models.PositiveSmallIntegerField()
    price = models.PositiveIntegerField(default=0, help_text="FCFA, 0 si inclus dans l'abonnement")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["starts_at"]


class ClassBooking(models.Model):
    gym_class = models.ForeignKey(GymClass, on_delete=models.CASCADE, related_name="bookings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="class_bookings")
    created_at = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)  # payé en ligne ; sinon réglé sur place
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["gym_class", "user"], name="one_seat_per_member")]


class GymReview(models.Model):
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gym_reviews")
    rating = models.PositiveSmallIntegerField()  # 1 à 5
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["gym", "user"], name="one_review_per_member")]


class MembershipRequest(models.Model):
    """Demande de formule envoyée à la salle. Le paiement se fait sur place."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Acceptée"
        DECLINED = "declined", "Refusée"
        CANCELLED = "cancelled", "Annulée"

    plan = models.ForeignKey(GymPlan, on_delete=models.CASCADE, related_name="requests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership_requests")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
