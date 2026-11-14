from django.conf import settings
from django.db import models


class Post(models.Model):
    """Une publication simple : du texte, et au plus une demande de binôme."""

    class Kind(models.TextChoices):
        TEXT = "text", "Publication"
        BUDDY = "buddy", "Cherche un binôme"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.TEXT)
    body = models.CharField(max_length=600)
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL)
    starts_at = models.DateTimeField(null=True, blank=True)  # pour une demande de binôme
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
