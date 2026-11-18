import uuid
from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Une notification dans l'app. L'envoi push (téléphone) se branchera plus tard sur le même modèle."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=240, blank=True)
    link = models.CharField(max_length=120, blank=True)  # route de l'app à ouvrir au clic
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "-created_at"])]
