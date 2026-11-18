import uuid
from django.conf import settings
from django.db import models


class Listing(models.Model):
    """Une annonce : n'importe quel membre peut vendre, avec un compte normal."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Category(models.TextChoices):
        WEIGHTS = "weights", "Poids"
        MACHINES = "machines", "Machines"
        CLOTHING = "clothing", "Tenues"
        ACCESSORIES = "accessories", "Accessoires"

    class Condition(models.TextChoices):
        NEW = "new", "Neuf"
        VERY_GOOD = "very_good", "Très bon état"
        OK = "ok", "Correct"

    class Status(models.TextChoices):
        ACTIVE = "active", "En vente"
        SOLD = "sold", "Vendu"
        HIDDEN = "hidden", "Retiré"

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=80)
    description = models.CharField(max_length=500, blank=True)
    price = models.PositiveIntegerField(help_text="FCFA")
    category = models.CharField(max_length=12, choices=Category.choices)
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.VERY_GOOD)
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL, related_name="listings")
    handover_at_gym = models.BooleanField(default=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "category", "-created_at"])]

    def __str__(self):
        return f"{self.title} ({self.price} F)"


class ListingPhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listings/%Y/%m/")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class Report(models.Model):
    """Signalement d'une annonce par un membre, traité dans le back-office."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Reason(models.TextChoices):
        SCAM = "scam", "Arnaque suspectée"
        FORBIDDEN = "forbidden", "Article interdit"
        WRONG = "wrong", "Annonce trompeuse"
        OTHER = "other", "Autre"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    reason = models.CharField(max_length=10, choices=Reason.choices)
    detail = models.CharField(max_length=300, blank=True)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["listing", "reporter"], name="one_report_per_member")]
