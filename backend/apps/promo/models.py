import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class Feature(models.Model):
    """Une mise à la une : un contenu mis en avant pendant une durée, dans le fil et en tête des listes.

    Pour l'instant c'est l'équipe qui l'accorde (gratuitement). Les champs `sponsored`, `price_fcfa` et
    `payment_reference` sont prévus pour qu'elle devienne payante sans changer le fonctionnement."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Kind(models.TextChoices):
        POST = "post", "Publication"
        PRO = "pro", "Professionnel"
        GYM = "gym", "Salle"
        LISTING = "listing", "Annonce"

    class Status(models.TextChoices):
        PENDING = "pending", "Demandée"
        APPROVED = "approved", "Accordée"
        REJECTED = "rejected", "Refusée"
        CANCELLED = "cancelled", "Arrêtée"

    kind = models.CharField(max_length=8, choices=Kind.choices)
    post = models.ForeignKey("feed.Post", null=True, blank=True, on_delete=models.CASCADE, related_name="features")
    pro = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="features")
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.CASCADE, related_name="features")
    listing = models.ForeignKey("market.Listing", null=True, blank=True, on_delete=models.CASCADE, related_name="features")
    scope_commune = models.CharField(max_length=60, blank=True)  # vide = pour tout le monde
    requested_days = models.PositiveSmallIntegerField(default=7)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    sponsored = models.BooleanField(default=False)  # « Sponsorisé » (payé) plutôt que « À la une » (éditorial)
    price_fcfa = models.PositiveIntegerField(null=True, blank=True)
    payment_reference = models.CharField(max_length=60, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    note = models.CharField(max_length=200, blank=True)
    views = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "starts_at", "ends_at"])]

    @property
    def target(self):
        return getattr(self, self.kind)


class FeatureEvent(models.Model):
    """Une vue ou un clic, compté une seule fois par membre et par jour pour que les chiffres restent honnêtes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    feature = models.ForeignKey(Feature, on_delete=models.CASCADE, related_name="events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=5)  # view | click
    day = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["feature", "user", "kind", "day"], name="one_event_per_user_day")]
