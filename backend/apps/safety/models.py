import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class Block(models.Model):
    """Un membre en bloque un autre : ils ne se voient plus et ne peuvent plus se parler."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="one_block_per_pair"),
            models.CheckConstraint(condition=~Q(blocker=models.F("blocked")), name="no_self_block"),
        ]


class ContentReport(models.Model):
    """Signalement d'un membre ou d'une publication, traité par l'équipe."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Kind(models.TextChoices):
        USER = "user", "Membre"
        POST = "post", "Publication"

    class Reason(models.TextChoices):
        HARASSMENT = "harassment", "Harcèlement ou comportement déplacé"
        SCAM = "scam", "Arnaque"
        INAPPROPRIATE = "inappropriate", "Contenu inapproprié"
        FAKE = "fake", "Faux profil"
        OTHER = "other", "Autre"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    kind = models.CharField(max_length=4, choices=Kind.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="reports_received")
    post = models.ForeignKey("feed.Post", null=True, blank=True, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=14, choices=Reason.choices)
    detail = models.CharField(max_length=300, blank=True)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["reporter", "user"], condition=Q(kind="user"), name="one_user_report_per_reporter"),
            models.UniqueConstraint(fields=["reporter", "post"], condition=Q(kind="post"), name="one_post_report_per_reporter"),
        ]
