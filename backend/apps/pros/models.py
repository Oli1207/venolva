from django.conf import settings
from django.db import models
from django.utils import timezone


class ProProfile(models.Model):
    """Dossier d'un professionnel. La coche verte n'est donnée qu'après validation par l'équipe."""

    class Status(models.TextChoices):
        PENDING = "pending", "En cours de vérification"
        APPROVED = "approved", "Validé"
        REJECTED = "rejected", "Refusé"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pro_profile")
    speciality = models.CharField(max_length=80, blank=True)
    bio = models.CharField(max_length=300, blank=True)
    credential = models.CharField(max_length=160, help_text="Numéro d'ordre, diplôme ou registre")
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL, related_name="pros")
    years_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    review_note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def approve(self):
        self.status = self.Status.APPROVED
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_at"])
        self.user.pro_verified = True
        self.user.save(update_fields=["pro_verified"])

    def reject(self, note=""):
        self.status = self.Status.REJECTED
        self.review_note = note[:200]
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "review_note", "reviewed_at"])
        self.user.pro_verified = False
        self.user.save(update_fields=["pro_verified"])

    def __str__(self):
        return f"{self.user} ({self.user.pro_type})"


class Service(models.Model):
    class Kind(models.TextChoices):
        TRIAL = "trial", "Séance d'essai"
        SINGLE = "single", "Séance"
        DUO = "duo", "Séance à deux"
        CONSULTATION = "consultation", "Consultation"
        FOLLOWUP = "followup", "Suivi"
        PLAN = "plan", "Plan personnalisé"
        WORKSHOP = "workshop", "Atelier collectif"

    MODES = ("gym", "home", "online")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=14, choices=Kind.choices, default=Kind.SINGLE)
    duration_min = models.PositiveSmallIntegerField(default=60)
    price = models.PositiveIntegerField(help_text="FCFA")
    modes = models.JSONField(default=list)  # sous-ensemble de MODES
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=240, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price", "id"]

    @property
    def is_duo(self) -> bool:
        return self.kind == self.Kind.DUO


class Availability(models.Model):
    """Plage hebdomadaire pendant laquelle le pro prend des rendez-vous."""

    pro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="availabilities")
    weekday = models.PositiveSmallIntegerField()  # 0 = lundi
    start = models.TimeField()
    end = models.TimeField()

    class Meta:
        ordering = ["weekday", "start"]


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmée"
        DECLINED = "declined", "Refusée"
        CANCELLED = "cancelled", "Annulée"
        DONE = "done", "Terminée"

    class Payment(models.TextChoices):
        UNPAID = "unpaid", "À payer"
        PARTIAL = "partial", "Partiellement payée"
        PAID = "paid", "Payée"

    class Method(models.TextChoices):
        CASH = "cash", "Sur place"
        ORANGE = "orange_money", "Orange Money"
        WAVE = "wave", "Wave"
        MTN = "mtn_momo", "MTN MoMo"

    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="bookings")
    pro = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings_received")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings_made")
    partner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings_invited"
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    mode = models.CharField(max_length=6, default="gym")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=8, choices=Payment.choices, default=Payment.UNPAID)
    payment_method = models.CharField(max_length=14, choices=Method.choices, default=Method.CASH)
    price_total = models.PositiveIntegerField()
    price_client = models.PositiveIntegerField()  # part du client (la moitié si séance à deux)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["pro", "starts_at"]), models.Index(fields=["client", "starts_at"])]

    BLOCKING = ("pending", "confirmed")
