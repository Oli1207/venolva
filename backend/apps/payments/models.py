from django.conf import settings
from django.db import models


class Payment(models.Model):
    """Un paiement en ligne. L'argent n'est considéré reçu qu'après confirmation signée du prestataire."""

    class Purpose(models.TextChoices):
        BOOKING = "booking", "Réservation d'un pro"
        CLASS = "class", "Cours collectif"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payé"
        FAILED = "failed", "Échoué"
        EXPIRED = "expired", "Remplacé"
        REVIEW = "review", "À vérifier (montant inattendu)"
        DUPLICATE = "duplicate", "Doublon à rembourser"
        REFUND_DUE = "refund_due", "À rembourser"
        REFUNDED = "refunded", "Remboursé"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    purpose = models.CharField(max_length=8, choices=Purpose.choices)
    target_id = models.PositiveIntegerField()
    amount = models.PositiveIntegerField(help_text="FCFA")
    fee = models.PositiveIntegerField(default=0, help_text="Part de Djinzin, en FCFA")
    net = models.PositiveIntegerField(default=0, help_text="Part à reverser au vendeur du service, en FCFA")
    provider = models.CharField(max_length=10)  # paystack | jeko
    method = models.CharField(max_length=12)
    reference = models.CharField(max_length=60, unique=True)
    provider_payment_id = models.CharField(max_length=80, blank=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    # Reversement : qui doit recevoir la part « net », quand le service est rendu, et dans quel lot elle a été versée.
    payee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="earnings")
    service_ends_at = models.DateTimeField(null=True, blank=True)
    payout = models.ForeignKey("Payout", null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    commission_pct = models.PositiveSmallIntegerField(default=0)  # taux appliqué à ce paiement, conservé pour l'historique
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reference = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose", "target_id"]), models.Index(fields=["payee", "status", "payout"])]

    def __str__(self):
        return f"{self.reference} {self.amount} F ({self.status})"


class WebhookEvent(models.Model):
    """Journal des notifications reçues des prestataires (jamais de données de carte ni de numéro)."""

    class Outcome(models.TextChoices):
        PROCESSED = "processed", "Traité"
        IGNORED = "ignored", "Ignoré"
        UNKNOWN = "unknown", "Référence inconnue"
        REJECTED = "rejected", "Rejeté"

    provider = models.CharField(max_length=10)
    event = models.CharField(max_length=60, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    signature_valid = models.BooleanField(default=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    detail = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PayoutAccount(models.Model):
    """Où verser l'argent d'un pro ou d'une salle (mobile money)."""

    class Method(models.TextChoices):
        WAVE = "wave", "Wave"
        ORANGE = "orange", "Orange Money"
        MTN = "mtn", "MTN MoMo"
        MOOV = "moov", "Moov Money"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payout_account")
    method = models.CharField(max_length=8, choices=Method.choices)
    number = models.CharField(max_length=14)  # numéro ivoirien normalisé
    holder_name = models.CharField(max_length=80)
    updated_at = models.DateTimeField(auto_now=True)


class Payout(models.Model):
    """Un reversement : la somme des parts « net » d'un pro ou d'une salle, versée en une fois."""

    class Status(models.TextChoices):
        PENDING = "pending", "À verser"
        PAID = "paid", "Versé"
        CANCELLED = "cancelled", "Annulé"

    payee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payouts")
    amount = models.PositiveIntegerField(help_text="FCFA")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    # Copie du compte au moment de la création : modifier son compte ensuite ne change pas un reversement en cours.
    method = models.CharField(max_length=8)
    number = models.CharField(max_length=14)
    holder_name = models.CharField(max_length=80)
    reference = models.CharField(max_length=80, blank=True)  # référence du virement, saisie par l'administrateur
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
