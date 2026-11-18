from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models


class Ambassador(models.Model):
    """Une personne qui représente Djinzin et touche un pourcentage de ce que la plateforme gagne."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ambassador")
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ambassadeur {self.user}"


class Contract(models.Model):
    """Un contrat de durée fixe (6 mois par défaut), renouvelable par un nouveau contrat.

    Base du pourcentage : les commissions que Djinzin perçoit (jamais l'argent des pros), une fois la séance rendue
    et le délai d'attente passé, donc après toute possibilité de remboursement."""

    ambassador = models.ForeignKey(Ambassador, on_delete=models.CASCADE, related_name="contracts")
    start_date = models.DateField()
    end_date = models.DateField()  # dernier jour inclus
    share_pct = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    signed_at = models.DateField(null=True, blank=True)  # tant qu'il est vide, le contrat n'est qu'un brouillon
    terminated_at = models.DateField(null=True, blank=True)
    termination_note = models.CharField(max_length=300, blank=True)
    renewal_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="renewals")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def state(self, today: date | None = None) -> str:
        """draft, upcoming, active, ended ou terminated."""
        today = today or date.today()
        if self.terminated_at:
            return "terminated"
        if self.signed_at is None:
            return "draft"
        if today < self.start_date:
            return "upcoming"
        return "ended" if today > self.end_date else "active"

    @property
    def effective_end(self) -> date:
        """Dernier jour où le contrat produit des gains (une résiliation anticipée raccourcit la durée)."""
        return min(self.end_date, self.terminated_at) if self.terminated_at else self.end_date

    def earns(self) -> bool:
        """Un brouillon non signé ne rapporte rien."""
        return self.signed_at is not None


class Statement(models.Model):
    """Relevé mensuel : ce que l'ambassadeur a gagné sur un mois, figé au moment où on le génère."""

    class Status(models.TextChoices):
        PENDING = "pending", "À verser"
        PAID = "paid", "Versé"
        CANCELLED = "cancelled", "Annulé"

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="statements")
    month = models.DateField()  # premier jour du mois
    fees_total = models.PositiveIntegerField()  # commissions de Djinzin prises en compte (FCFA)
    share_pct = models.PositiveSmallIntegerField()  # taux appliqué, conservé pour l'historique
    amount = models.PositiveIntegerField()  # part de l'ambassadeur (FCFA)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reference = models.CharField(max_length=80, blank=True)  # référence du virement
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month"]
        constraints = [models.UniqueConstraint(fields=["contract", "month"], condition=~models.Q(status="cancelled"), name="one_live_statement_per_month")]


class StatementLine(models.Model):
    """Un paiement compté dans un relevé. Un paiement ne peut apparaître qu'une seule fois, tous relevés confondus."""

    statement = models.ForeignKey(Statement, on_delete=models.CASCADE, related_name="lines")
    payment = models.OneToOneField("payments.Payment", on_delete=models.PROTECT, related_name="statement_line")
    fee = models.PositiveIntegerField()
