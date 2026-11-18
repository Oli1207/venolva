"""Calcul des gains d'une ambassadrice, relevés mensuels et renouvellement de contrat."""
import calendar
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.backoffice.config import cfg
from apps.payments.models import Payment

from .models import Ambassador, Contract, Statement, StatementLine


class AmbassadorError(Exception):
    pass


def add_months(d: date, months: int) -> date:
    """d + months mois, en gardant un jour valide (31 janvier + 1 mois = 28 février)."""
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def term_end(start: date, months: int) -> date:
    """Dernier jour inclus d'un contrat de `months` mois qui commence à `start`."""
    return add_months(start, months) - timedelta(days=1)


def month_bounds(month: date) -> tuple[date, date]:
    return month.replace(day=1), month.replace(day=calendar.monthrange(month.year, month.month)[1])


def _aware(d: date, t: time) -> datetime:
    return timezone.make_aware(datetime.combine(d, t), timezone.get_current_timezone())


# --- Contrats ------------------------------------------------------------------------------------------------------------


def create_contract(ambassador: Ambassador, *, start: date, months: int | None = None, share_pct: int | None = None, actor=None, renewal_of=None) -> Contract:
    s = cfg()
    months = months if months is not None else s.ambassador_contract_months
    share_pct = share_pct if share_pct is not None else s.ambassador_share_pct
    if not 1 <= months <= 36:
        raise AmbassadorError("La durée doit être de 1 à 36 mois.")
    if not 0 <= share_pct <= 100:
        raise AmbassadorError("Le pourcentage doit être entre 0 et 100.")
    end = term_end(start, months)
    # Un contrat résilié n'occupe les dates que jusqu'à sa résiliation.
    clash = [c for c in ambassador.contracts.all() if c.start_date <= end and start <= c.effective_end]
    if clash:
        raise AmbassadorError("Ces dates chevauchent un autre contrat de cette personne.")
    return Contract.objects.create(ambassador=ambassador, start_date=start, end_date=end, share_pct=share_pct, created_by=actor, renewal_of=renewal_of)


def renew_contract(contract: Contract, *, months: int | None = None, share_pct: int | None = None, actor=None) -> Contract:
    """Prépare le contrat suivant (brouillon) : il commence le lendemain de la fin du précédent, aux mêmes conditions."""
    if contract.terminated_at:
        raise AmbassadorError("Un contrat résilié ne se renouvelle pas : crée un nouveau contrat.")
    if contract.renewals.filter(terminated_at__isnull=True).exists():
        raise AmbassadorError("Ce contrat a déjà un renouvellement.")
    return create_contract(
        contract.ambassador, start=contract.end_date + timedelta(days=1), months=months if months is not None else _months_between(contract),
        share_pct=share_pct if share_pct is not None else contract.share_pct, actor=actor, renewal_of=contract,
    )


def _months_between(c: Contract) -> int:
    """Durée d'un contrat en mois (pour renouveler à l'identique)."""
    for m in range(1, 37):
        if term_end(c.start_date, m) == c.end_date:
            return m
    return cfg().ambassador_contract_months


def sign_contract(contract: Contract, signed_at: date) -> Contract:
    if contract.terminated_at:
        raise AmbassadorError("Ce contrat est résilié.")
    if contract.signed_at:
        raise AmbassadorError("Ce contrat est déjà signé.")
    contract.signed_at = signed_at
    contract.save(update_fields=["signed_at"])
    return contract


def terminate_contract(contract: Contract, on: date, note: str) -> Contract:
    if contract.terminated_at:
        raise AmbassadorError("Ce contrat est déjà résilié.")
    if on < contract.start_date:
        on = contract.start_date
    contract.terminated_at = on
    contract.termination_note = note[:300]
    contract.save(update_fields=["terminated_at", "termination_note"])
    return contract


# --- Gains ---------------------------------------------------------------------------------------------------------------


def _share(fees: int, pct: int) -> int:
    return (fees * pct + 50) // 100  # arrondi au FCFA le plus proche


def eligible_payments(contract: Contract, until: date):
    """Paiements dont la commission compte pour ce contrat : encaissés, service rendu et délai d'attente écoulé
    (donc plus remboursables), pas encore comptés dans un relevé, et réglés pendant la durée du contrat."""
    hold = timedelta(days=cfg().payout_hold_days)
    until = min(until, contract.effective_end)
    return Payment.objects.filter(
        status="paid", fee__gt=0, statement_line__isnull=True,
        service_ends_at__gte=_aware(contract.start_date, time.min) - hold,
        service_ends_at__lte=_aware(until, time.max) - hold,
    )


def preview(contract: Contract, until: date | None = None) -> dict:
    """Estimation de ce qui est déjà acquis et pas encore passé dans un relevé."""
    if not contract.earns():
        return {"fees": 0, "amount": 0, "payments": 0}
    until = min(until or timezone.localdate(), timezone.localdate())
    agg = eligible_payments(contract, until).aggregate(fees=Sum("fee"))
    fees = agg["fees"] or 0
    return {"fees": fees, "amount": _share(fees, contract.share_pct), "payments": eligible_payments(contract, until).count()}


def generate_statement(contract: Contract, month: date, actor=None) -> Statement:
    """Relevé d'un mois terminé. Il reprend aussi ce qui n'avait pas pu être compté les mois précédents."""
    first, last = month_bounds(month)
    if not contract.earns():
        raise AmbassadorError("Le contrat n'est pas signé : il ne produit pas de gains.")
    if timezone.localdate() <= last:
        raise AmbassadorError("Ce mois n'est pas terminé.")
    if last < contract.start_date or first > contract.effective_end:
        raise AmbassadorError("Ce mois est en dehors de la durée du contrat.")
    if Statement.objects.filter(contract=contract, month=first).exclude(status="cancelled").exists():
        raise AmbassadorError("Le relevé de ce mois existe déjà.")
    with transaction.atomic():
        payments = list(eligible_payments(contract, last).select_for_update())
        fees = sum(p.fee for p in payments)
        statement = Statement.objects.create(
            contract=contract, month=first, fees_total=fees, share_pct=contract.share_pct, amount=_share(fees, contract.share_pct), created_by=actor,
        )
        StatementLine.objects.bulk_create([StatementLine(statement=statement, payment=p, fee=p.fee) for p in payments])
        return statement


def mark_paid(statement: Statement, reference: str) -> Statement:
    if statement.status != Statement.Status.PENDING:
        raise AmbassadorError("Ce relevé n'est plus à verser.")
    if not reference.strip():
        raise AmbassadorError("Indique la référence du virement.")
    statement.status = Statement.Status.PAID
    statement.reference = reference.strip()[:80]
    statement.paid_at = timezone.now()
    statement.save(update_fields=["status", "reference", "paid_at"])
    return statement


def cancel_statement(statement: Statement) -> Statement:
    """Annule un relevé non versé : ses paiements pourront être comptés dans un autre relevé."""
    if statement.status != Statement.Status.PENDING:
        raise AmbassadorError("Seul un relevé « à verser » peut être annulé.")
    with transaction.atomic():
        statement.lines.all().delete()
        statement.status = Statement.Status.CANCELLED
        statement.save(update_fields=["status"])
    return statement


def totals(ambassador: Ambassador) -> dict:
    qs = Statement.objects.filter(contract__ambassador=ambassador)
    return {
        "pending": qs.filter(status="pending").aggregate(s=Sum("amount"))["s"] or 0,
        "paid": qs.filter(status="paid").aggregate(s=Sum("amount"))["s"] or 0,
    }


def current_contract(ambassador: Ambassador, today: date | None = None) -> Contract | None:
    """Le contrat en cours, sinon le prochain, sinon le plus récent."""
    today = today or date.today()
    contracts = list(ambassador.contracts.all())
    for want in ("active", "upcoming", "draft", "ended", "terminated"):
        found = [c for c in contracts if c.state(today) == want]
        if found:
            return sorted(found, key=lambda c: c.start_date)[-1 if want in ("ended", "terminated") else 0]
    return None
