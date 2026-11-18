"""Choix du prestataire, création d'un paiement et finalisation (idempotente) après confirmation."""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.backoffice.config import cfg, commission_pct
from apps.gyms.models import ClassBooking
from apps.notifications.services import notify
from apps.pros.models import Booking

from .exceptions import PaymentUnavailable
from .models import Payment, Payout, PayoutAccount
from .providers import jeko, paystack

logger = logging.getLogger(__name__)

METHOD_LABELS = {"wave": "Wave", "orange": "Orange Money", "mtn": "MTN MoMo", "moov": "Moov Money", "djamo": "Djamo",
                 "mobile": "Mobile money", "card": "Carte bancaire"}


class PaymentRefused(Exception):
    """La demande de paiement n'est pas valable (réservation déjà payée, mauvais statut…)."""


# --- Moyens et prestataires -------------------------------------------------------------------------------------


def _usable():
    mode = cfg().payment_mode
    return (
        jeko.is_configured() and mode in ("auto", "jeko"),
        paystack.is_configured() and mode in ("auto", "paystack"),
    )


def available_methods() -> list[dict]:
    """Moyens proposés à l'acheteur selon les clés configurées."""
    jeko_ok, paystack_ok = _usable()
    out = []
    if jeko_ok:
        out += [{"code": m, "label": METHOD_LABELS[m], "provider": "jeko"} for m in ("wave", "orange", "mtn", "moov")]
    elif paystack_ok:
        out.append({"code": "mobile", "label": METHOD_LABELS["mobile"], "provider": "paystack"})
    if paystack_ok:
        out.append({"code": "card", "label": METHOD_LABELS["card"], "provider": "paystack"})
    return out


def providers_for(method: str) -> list[str]:
    """Prestataires à essayer, dans l'ordre. Jeko d'abord pour le mobile money, avec Paystack en secours."""
    jeko_ok, paystack_ok = _usable()
    if method == "card":
        return ["paystack"] if paystack_ok else []
    if method in jeko.METHODS or method == "mobile":
        order = []
        if jeko_ok and method in jeko.METHODS:
            order.append("jeko")
        if paystack_ok:
            order.append("paystack")
        return order
    return []


# --- Cible du paiement ---------------------------------------------------------------------------------------------


def _paid_sum(booking: Booking) -> int:
    return Payment.objects.filter(purpose="booking", target_id=booking.pk, status="paid").aggregate(s=Sum("amount"))["s"] or 0


def resolve_target(user, purpose: str, target_id: int):
    """Renvoie (objet, montant en FCFA, bénéficiaire, fin du service). Lève PaymentRefused si ce paiement n'est pas permis."""
    if purpose == Payment.Purpose.BOOKING:
        booking = Booking.objects.select_related("pro", "client", "partner").filter(pk=target_id).first()
        if booking is None or user.pk not in (booking.client_id, booking.partner_id):
            raise PaymentRefused("Réservation introuvable.")
        if booking.status != Booking.Status.CONFIRMED:
            raise PaymentRefused("Tu pourras payer en ligne quand le professionnel aura confirmé la réservation.")
        if booking.payment_status == Booking.Payment.PAID:
            raise PaymentRefused("Cette réservation est déjà payée.")
        if booking.starts_at < timezone.now() - timedelta(hours=3):
            raise PaymentRefused("Cette séance est passée.")
        if Payment.objects.filter(user=user, purpose="booking", target_id=booking.pk, status="paid").exists():
            raise PaymentRefused("Tu as déjà payé ta part.")
        amount = booking.price_client if user.pk == booking.client_id else booking.price_total - booking.price_client
        if amount <= 0:
            raise PaymentRefused("Rien à payer.")
        return booking, amount, booking.pro, booking.ends_at
    if purpose == Payment.Purpose.CLASS:
        seat = ClassBooking.objects.select_related("gym_class", "gym_class__gym").filter(pk=target_id, user=user).first()
        if seat is None:
            raise PaymentRefused("Réservation introuvable.")
        if seat.paid:
            raise PaymentRefused("Ce cours est déjà payé.")
        if seat.gym_class.price <= 0:
            raise PaymentRefused("Ce cours est inclus dans l'abonnement.")
        if seat.gym_class.starts_at <= timezone.now() or not seat.gym_class.active:
            raise PaymentRefused("Ce cours n'est plus disponible.")
        gc = seat.gym_class
        return seat, gc.price, gc.gym.owner, gc.starts_at + timedelta(minutes=gc.duration_min)
    raise PaymentRefused("Type de paiement inconnu.")


# --- Création -------------------------------------------------------------------------------------------------------


def start_payment(user, purpose: str, target_id: int, method: str) -> Payment:
    _, amount, payee, ends_at = resolve_target(user, purpose, target_id)
    providers = providers_for(method)
    if not providers:
        raise PaymentRefused("Ce moyen de paiement n'est pas disponible.")

    reference = f"DJZ-{purpose[0]}{target_id}-{secrets.token_hex(5)}"
    callback = f"{settings.FRONTEND_URL}/paiement/retour?ref={reference}"
    last_error = None
    for provider in providers:
        try:
            if provider == "jeko":
                data = jeko.create_payment_request(amount_fcfa=amount, reference=reference, success_url=callback, error_url=callback, method=method)
                url, provider_id = data.get("redirectUrl"), str(data.get("id") or "")
            else:
                data = paystack.initialize(
                    email=user.email or f"u{user.pk}@{settings.PAYMENT_EMAIL_DOMAIN}", amount_fcfa=amount, reference=reference,
                    callback_url=callback, metadata={"purpose": purpose, "target": target_id, "user": user.pk},
                )
                url, provider_id = data.get("authorization_url"), ""
        except PaymentUnavailable as exc:
            logger.warning("Prestataire %s indisponible, essai du suivant", provider)
            last_error = exc
            continue
        if not url:
            last_error = PaymentUnavailable()
            continue
        pct = commission_pct(payee, purpose)
        fee = round(amount * pct / 100)
        with transaction.atomic():
            # Un nouveau paiement remplace les tentatives non abouties pour la même cible.
            Payment.objects.filter(user=user, purpose=purpose, target_id=target_id, status="pending").update(status="expired")
            return Payment.objects.create(
                user=user, purpose=purpose, target_id=target_id, amount=amount, fee=fee, net=amount - fee,
                provider=provider, method=method, reference=reference, provider_payment_id=provider_id, checkout_url=url,
                payee=payee, service_ends_at=ends_at, commission_pct=pct,
            )
    raise last_error or PaymentUnavailable()


# --- Finalisation -----------------------------------------------------------------------------------------------------


def amount_matches(provider: str, expected_fcfa: int, received: int) -> bool:
    """Paystack et Jeko expriment les montants en centimes. Pour Jeko la doc ne tranche pas sur les webhooks :
    on accepte uniquement les deux lectures exactes (centimes ou FCFA entiers), jamais une valeur approchée."""
    if provider == "paystack":
        return received == expected_fcfa * 100
    return received in (expected_fcfa * 100, expected_fcfa)


def _apply(payment: Payment):
    if payment.purpose == Payment.Purpose.BOOKING:
        booking = Booking.objects.select_for_update().get(pk=payment.target_id)
        paid = _paid_sum(booking)
        booking.payment_status = Booking.Payment.PAID if paid >= booking.price_total else Booking.Payment.PARTIAL
        booking.save(update_fields=["payment_status"])
    else:
        ClassBooking.objects.filter(pk=payment.target_id).update(paid=True, paid_at=payment.paid_at)


def fulfill(reference: str, *, received: int, currency: str, paid_at=None) -> Payment | None:
    """Marque le paiement comme payé si le montant est exact. Idempotent : un second appel ne change rien."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(reference=reference).first()
        if payment is None:
            return None
        if payment.status in ("paid", "duplicate"):
            return payment
        expected_currency = settings.JEKO_CURRENCY if payment.provider == "jeko" else settings.PAYSTACK_CURRENCY
        if not amount_matches(payment.provider, payment.amount, received) or (currency and currency != expected_currency):
            logger.error("Montant ou devise inattendus pour un paiement : à vérifier à la main")
            payment.status = Payment.Status.REVIEW
            payment.save(update_fields=["status"])
            return payment
        if Payment.objects.filter(user=payment.user, purpose=payment.purpose, target_id=payment.target_id, status="paid").exclude(pk=payment.pk).exists():
            payment.status = Payment.Status.DUPLICATE  # il a payé deux fois : le second paiement est à rembourser
            payment.paid_at = paid_at or timezone.now()
            payment.save(update_fields=["status", "paid_at"])
            return payment
        payment.status = Payment.Status.PAID
        payment.paid_at = paid_at or timezone.now()
        payment.save(update_fields=["status", "paid_at"])
        _apply(payment)
    price = f"{payment.amount:,}".replace(",", " ")
    notify(payment.payee, "payment_received", f"Paiement reçu : {price} F", "", "/revenus")
    notify(payment.user, "payment_confirmed", f"Paiement de {price} F confirmé", "", "/seances?tab=bookings")
    return payment


def verify_with_provider(payment: Payment) -> Payment:
    """Repli si le webhook tarde : interroge le prestataire et finalise si le paiement est réussi."""
    if payment.status != Payment.Status.PENDING:
        return payment
    if payment.provider == "paystack":
        data = paystack.verify(payment.reference)
        if data.get("status") == "success":
            from django.utils.dateparse import parse_datetime

            return fulfill(payment.reference, received=int(data.get("amount") or 0), currency=str(data.get("currency") or ""),
                           paid_at=parse_datetime(str(data.get("paid_at") or ""))) or payment
    elif payment.provider == "jeko" and payment.provider_payment_id:
        data = jeko.get_payment_request(payment.provider_payment_id)
        tx = data.get("transaction") or {}
        if data.get("status") == "success" and tx:
            amount = tx.get("amount") or {}
            return fulfill(payment.reference, received=int(amount.get("amount") or 0), currency=str(amount.get("currency") or "")) or payment
    payment.refresh_from_db()
    return payment


# --- Remboursements ---------------------------------------------------------------------------------------------------


def flag_refunds(purpose: str, target_id: int, *, refund: bool) -> int:
    """Quand une réservation payée est annulée : si le client doit être remboursé, les paiements passent « à rembourser »
    (l'administrateur rembourse ensuite chez le prestataire). Sinon ils restent payés et le vendeur garde la somme.
    Un paiement déjà inclus dans un reversement n'est pas touché."""
    Payment.objects.filter(purpose=purpose, target_id=target_id, status="pending").update(status="expired")
    if not refund:
        return 0
    return Payment.objects.filter(purpose=purpose, target_id=target_id, status="paid", payout__isnull=True).update(status="refund_due")


def client_refund_applies(starts_at) -> bool:
    """Annulation par le client : remboursé s'il annule assez tôt (réglage « annulation gratuite »)."""
    return starts_at - timezone.now() >= timedelta(hours=cfg().free_cancel_hours)


def mark_refunded(payment: Payment, reference: str = "") -> Payment:
    if payment.status not in ("refund_due", "duplicate", "review"):
        raise PaymentRefused("Ce paiement n'est pas à rembourser.")
    payment.status = Payment.Status.REFUNDED
    payment.refunded_at = timezone.now()
    payment.refund_reference = reference[:80]
    payment.save(update_fields=["status", "refunded_at", "refund_reference"])
    return payment


def accept_review(payment: Payment) -> Payment:
    """Après vérification manuelle d'un montant inattendu, l'administrateur peut le valider comme payé."""
    if payment.status != "review":
        raise PaymentRefused("Ce paiement n'est pas à vérifier.")
    with transaction.atomic():
        payment.status = Payment.Status.PAID
        payment.paid_at = payment.paid_at or timezone.now()
        payment.save(update_fields=["status", "paid_at"])
        _apply(payment)
    return payment


# --- Reversements ------------------------------------------------------------------------------------------------------


class PayoutError(Exception):
    pass


def eligible_payments(payee, now=None):
    """Paiements encaissés dont le service est rendu depuis plus que le délai d'attente et pas encore reversés."""
    now = now or timezone.now()
    cutoff = now - timedelta(days=cfg().payout_hold_days)
    return Payment.objects.filter(payee=payee, status="paid", payout__isnull=True, service_ends_at__lte=cutoff)


def _sum_net(qs) -> int:
    return qs.aggregate(s=Sum("net"))["s"] or 0


def balance_for(payee) -> dict:
    """Ce qu'un pro ou une salle a gagné : disponible, en attente du délai, en cours de versement, déjà versé."""
    collected = Payment.objects.filter(payee=payee, status="paid", payout__isnull=True)
    available = _sum_net(eligible_payments(payee))
    return {
        "available": available,
        "waiting": _sum_net(collected) - available,
        "in_payout": Payout.objects.filter(payee=payee, status="pending").aggregate(s=Sum("amount"))["s"] or 0,
        "paid_out": Payout.objects.filter(payee=payee, status="paid").aggregate(s=Sum("amount"))["s"] or 0,
        "refund_pending": _sum_net(Payment.objects.filter(payee=payee, status="refund_due")),
    }


def create_payout(payee, actor) -> Payout:
    """Rassemble tout ce qui est disponible pour ce bénéficiaire dans un reversement « à verser »."""
    with transaction.atomic():
        payments = list(eligible_payments(payee).select_for_update())
        total = sum(p.net for p in payments)
        if not payments or total <= 0:
            raise PayoutError("Rien à reverser pour le moment.")
        minimum = cfg().min_payout_fcfa
        if total < minimum:
            raise PayoutError(f"Le solde disponible ({total} F) est sous le minimum de reversement ({minimum} F).")
        account = PayoutAccount.objects.filter(user=payee).first()
        if account is None:
            raise PayoutError("Ce bénéficiaire n'a pas encore indiqué où recevoir son argent.")
        payout = Payout.objects.create(
            payee=payee, amount=total, method=account.method, number=account.number, holder_name=account.holder_name, created_by=actor,
        )
        Payment.objects.filter(pk__in=[p.pk for p in payments]).update(payout=payout)
        return payout


def mark_payout_paid(payout: Payout, reference: str) -> Payout:
    if payout.status != Payout.Status.PENDING:
        raise PayoutError("Ce reversement n'est plus à verser.")
    if not reference.strip():
        raise PayoutError("Indique la référence du virement.")
    payout.status = Payout.Status.PAID
    payout.reference = reference.strip()[:80]
    payout.paid_at = timezone.now()
    payout.save(update_fields=["status", "reference", "paid_at"])
    return payout


def cancel_payout(payout: Payout) -> Payout:
    """Annule un reversement non versé : les paiements redeviennent disponibles."""
    if payout.status != Payout.Status.PENDING:
        raise PayoutError("Seul un reversement « à verser » peut être annulé.")
    with transaction.atomic():
        Payment.objects.filter(payout=payout).update(payout=None)
        payout.status = Payout.Status.CANCELLED
        payout.save(update_fields=["status"])
    return payout
