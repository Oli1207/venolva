from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PlatformSettings(models.Model):
    """Réglages de la plateforme, modifiables depuis l'administration (une seule ligne).

    Les valeurs par défaut reproduisent le comportement d'avant : rien ne change tant qu'on ne les modifie pas."""

    class PaymentMode(models.TextChoices):
        AUTO = "auto", "Jeko puis Paystack"
        JEKO = "jeko", "Jeko uniquement"
        PAYSTACK = "paystack", "Paystack uniquement"

    # Finance
    commission_booking_pct = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(50)])
    commission_class_pct = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(50)])
    payment_mode = models.CharField(max_length=10, choices=PaymentMode.choices, default=PaymentMode.AUTO)
    payout_hold_days = models.PositiveSmallIntegerField(default=2, validators=[MaxValueValidator(30)])
    min_payout_fcfa = models.PositiveIntegerField(default=5000)
    free_cancel_hours = models.PositiveSmallIntegerField(default=24, validators=[MaxValueValidator(168)])
    price_min_fcfa = models.PositiveIntegerField(default=500)
    price_max_fcfa = models.PositiveIntegerField(default=5_000_000)
    # Réservations et marché
    booking_lead_hours = models.PositiveSmallIntegerField(default=1, validators=[MaxValueValidator(72)])
    max_active_listings = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_listing_photos = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1), MaxValueValidator(10)])
    # Connexion par code
    otp_ttl_seconds = models.PositiveSmallIntegerField(default=300, validators=[MinValueValidator(60), MaxValueValidator(1800)])
    otp_max_attempts = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(3), MaxValueValidator(10)])
    otp_max_requests_per_hour = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(20)])

    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "réglages de la plateforme"

    def save(self, *args, **kwargs):
        self.pk = 1  # une seule ligne
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "PlatformSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# Description de chaque réglage : sert à valider les modifications et à construire le formulaire de l'administration.
GROUPS = [("finance", "Finance"), ("bookings", "Réservations et marché"), ("auth", "Connexion par code")]
SCHEMA = [
    dict(key="commission_booking_pct", group="finance", label="Commission sur les réservations de pros", unit="%", min=0, max=50,
         help="Part de Djinzin retenue sur chaque réservation payée en ligne. Elle est déduite de ce que reçoit le pro, le client paie le même prix."),
    dict(key="commission_class_pct", group="finance", label="Commission sur les cours collectifs", unit="%", min=0, max=50,
         help="Même principe pour les cours payants des salles."),
    dict(key="payment_mode", group="finance", label="Prestataires de paiement", type="choice",
         choices=[{"value": v, "label": l} for v, l in PlatformSettings.PaymentMode.choices],
         help="Auto : Jeko pour le mobile money s'il est configuré, Paystack en secours et pour la carte."),
    dict(key="payout_hold_days", group="finance", label="Délai avant reversement", unit="jours", min=0, max=30,
         help="Après la séance, l'argent reste en attente ce nombre de jours avant de pouvoir être reversé (litiges, annulations)."),
    dict(key="min_payout_fcfa", group="finance", label="Reversement minimum", unit="FCFA", min=0, max=1_000_000,
         help="En dessous de ce solde, un reversement ne peut pas être créé."),
    dict(key="free_cancel_hours", group="finance", label="Annulation gratuite jusqu'à", unit="heures avant", min=0, max=168,
         help="Un client qui annule plus tôt est remboursé. Plus tard, le pro garde la somme. Si c'est le pro qui annule, le client est toujours remboursé."),
    dict(key="price_min_fcfa", group="finance", label="Prix minimum d'un article, service ou formule", unit="FCFA", min=100, max=1_000_000, help=""),
    dict(key="price_max_fcfa", group="finance", label="Prix maximum d'un article, service ou formule", unit="FCFA", min=1000, max=50_000_000, help=""),
    dict(key="booking_lead_hours", group="bookings", label="Délai minimum pour réserver", unit="heures", min=0, max=72,
         help="On ne peut pas réserver une séance qui commence dans moins de ce délai."),
    dict(key="max_active_listings", group="bookings", label="Annonces en vente par membre", unit="annonces", min=1, max=100, help=""),
    dict(key="max_listing_photos", group="bookings", label="Photos par annonce", unit="photos", min=1, max=10, help=""),
    dict(key="otp_ttl_seconds", group="auth", label="Durée de validité d'un code", unit="secondes", min=60, max=1800, help=""),
    dict(key="otp_max_attempts", group="auth", label="Essais par code", unit="essais", min=3, max=10, help="Au-delà, il faut demander un nouveau code."),
    dict(key="otp_max_requests_per_hour", group="auth", label="Codes demandés par numéro et par heure", unit="codes", min=1, max=20,
         help="Protège un numéro contre l'envoi massif de SMS."),
]
SCHEMA_BY_KEY = {s["key"]: s for s in SCHEMA}


class CommissionOverride(models.Model):
    """Commission particulière pour un vendeur (partenariat, offre de lancement…). Elle remplace le taux par défaut."""

    class Purpose(models.TextChoices):
        ALL = "all", "Tous les paiements"
        BOOKING = "booking", "Réservations de pros"
        CLASS = "class", "Cours collectifs"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="commission_overrides")
    purpose = models.CharField(max_length=8, choices=Purpose.choices, default=Purpose.ALL)
    pct = models.PositiveSmallIntegerField(validators=[MaxValueValidator(50)])
    note = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "purpose"], name="one_override_per_purpose")]


class AuditLog(models.Model):
    """Trace de chaque action d'administration : qui, quoi, quand, et la valeur avant et après."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=60, db_index=True)
    target = models.CharField(max_length=80, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


def audit(actor, action: str, target: str = "", **detail) -> AuditLog:
    return AuditLog.objects.create(actor=actor, action=action, target=target[:80], detail=detail)
