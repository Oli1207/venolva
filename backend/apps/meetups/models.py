from django.conf import settings
from django.db import models


class Meetup(models.Model):
    """Une séance à deux, proposée par un membre à un autre."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmée"
        DONE = "done", "Terminée"
        CANCELLED = "cancelled", "Annulée"

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organized_meetups")
    partner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invited_meetups")
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL)
    starts_at = models.DateTimeField()
    focus = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    organizer_arrived_at = models.DateTimeField(null=True, blank=True)
    partner_arrived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["status", "starts_at"])]

    def involves(self, user) -> bool:
        return user.pk in (self.organizer_id, self.partner_id)

    def other(self, user):
        return self.partner if user.pk == self.organizer_id else self.organizer
