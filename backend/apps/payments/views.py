import json
import logging

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import PaymentUnavailable
from .models import Payment, Payout, PayoutAccount, WebhookEvent
from .providers import jeko, paystack
from .services import PaymentRefused, available_methods, balance_for, fulfill, start_payment, verify_with_provider
from config.ids import as_uuid

logger = logging.getLogger(__name__)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["reference", "purpose", "target_id", "amount", "provider", "method", "status", "created_at", "paid_at"]


class MethodsView(APIView):
    """GET /api/payments/methods/ : moyens de paiement en ligne disponibles (selon les clés configurées)."""

    def get(self, request):
        return Response(available_methods())


class PaymentCreateView(APIView):
    """POST /api/payments/ {purpose: booking|class, target: <id>, method} : renvoie l'adresse de la page de paiement."""

    throttle_scope = "payment_init"

    def post(self, request):
        purpose, method = request.data.get("purpose"), request.data.get("method")
        target = as_uuid(request.data.get("target"))
        if target is None:
            return Response({"target": ["Cible invalide."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payment = start_payment(request.user, str(purpose), target, str(method))
        except PaymentRefused as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # PaymentUnavailable (503) est géré par DRF avec un message générique.
        return Response(
            {"reference": payment.reference, "checkout_url": payment.checkout_url, "provider": payment.provider, "amount": payment.amount},
            status=status.HTTP_201_CREATED,
        )


class PaymentDetailView(APIView):
    def get(self, request, reference):
        payment = get_object_or_404(Payment, reference=reference, user=request.user)
        return Response(PaymentSerializer(payment).data)


class PaymentVerifyView(APIView):
    """POST /api/payments/<ref>/verify/ : au retour de la page de paiement, vérifie auprès du prestataire."""

    throttle_scope = "payment_init"

    def post(self, request, reference):
        payment = get_object_or_404(Payment, reference=reference, user=request.user)
        try:
            payment = verify_with_provider(payment)
        except PaymentUnavailable:
            payment.refresh_from_db()  # on renvoie l'état connu, le webhook finira le travail
        return Response(PaymentSerializer(payment).data)


# --- Webhooks (sans JWT : l'authenticité repose uniquement sur la signature du corps brut) -----------------------------


def _log(provider, event, reference, outcome, detail="", signature_valid=True):
    WebhookEvent.objects.create(
        provider=provider, event=event[:60], reference=reference[:100], signature_valid=signature_valid, outcome=outcome, detail=detail[:200]
    )


class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "payment_webhook"

    def post(self, request):
        raw = request.body
        if not paystack.is_valid_signature(raw, request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")):
            _log("paystack", "", "", WebhookEvent.Outcome.REJECTED, "Signature invalide", signature_valid=False)
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw)
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        event = str(payload.get("event") or "")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        reference = str(data.get("reference") or "")
        if event != "charge.success":
            _log("paystack", event, reference, WebhookEvent.Outcome.IGNORED)
            return Response(status=status.HTTP_200_OK)
        try:
            received = int(data.get("amount") or 0)
        except (TypeError, ValueError):
            received = 0
        payment = fulfill(reference, received=received, currency=str(data.get("currency") or ""), paid_at=parse_datetime(str(data.get("paid_at") or "")))
        if payment is None:
            _log("paystack", event, reference, WebhookEvent.Outcome.UNKNOWN)
        else:
            _log("paystack", event, reference, WebhookEvent.Outcome.PROCESSED, f"Paiement {payment.status}")
        return Response(status=status.HTTP_200_OK)


class JekoWebhookView(APIView):
    """Répond 200 à tout événement authentique, même inconnu : Jeko désactive un webhook après des échecs répétés.
    Seule une signature invalide est refusée (401)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "payment_webhook"

    def post(self, request):
        raw = request.body
        event = str(request.META.get("HTTP_JEKO_EVENT", ""))[:60]
        if not jeko.is_valid_signature(raw, request.META.get("HTTP_JEKO_SIGNATURE", "")):
            _log("jeko", event, "", WebhookEvent.Outcome.REJECTED, "Signature invalide", signature_valid=False)
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(raw)
        except ValueError:
            _log("jeko", event, "", WebhookEvent.Outcome.REJECTED, "Corps illisible")
            return Response(status=status.HTTP_200_OK)
        details = payload.get("transactionDetails") if isinstance(payload.get("transactionDetails"), dict) else {}
        reference = str(details.get("reference") or "")
        if event != "TRANSACTION_COMPLETED" or payload.get("status") != "success":
            _log("jeko", event, reference, WebhookEvent.Outcome.IGNORED, "Événement non traité")
            return Response(status=status.HTTP_200_OK)
        amount = payload.get("amount") if isinstance(payload.get("amount"), dict) else {}
        try:
            received = int(amount.get("amount") or 0)
        except (TypeError, ValueError):
            received = 0
        payment = fulfill(reference, received=received, currency=str(amount.get("currency") or ""))
        if payment is None:
            _log("jeko", event, reference, WebhookEvent.Outcome.UNKNOWN, "Référence inconnue")
        else:
            _log("jeko", event, reference, WebhookEvent.Outcome.PROCESSED, f"Paiement {payment.status}")
        return Response(status=status.HTTP_200_OK)


# --- Revenus d'un pro ou d'une salle -------------------------------------------------------------------------------------


class PayoutAccountView(APIView):
    """GET puis PUT /api/my/payout-account/ : où recevoir mes reversements."""

    def get(self, request):
        a = PayoutAccount.objects.filter(user=request.user).first()
        return Response({"method": a.method, "number": a.number, "holder_name": a.holder_name} if a else None)

    def put(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from apps.accounts.models import normalize_phone

        method = request.data.get("method")
        holder = str(request.data.get("holder_name", "")).strip()
        if method not in dict(PayoutAccount.Method.choices):
            return Response({"method": ["Choisis un moyen de réception."]}, status=status.HTTP_400_BAD_REQUEST)
        if not 2 <= len(holder) <= 80:
            return Response({"holder_name": ["Indique le nom du titulaire du compte."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            number = normalize_phone(str(request.data.get("number", "")))
        except DjangoValidationError as exc:
            return Response({"number": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        PayoutAccount.objects.update_or_create(user=request.user, defaults={"method": method, "number": number, "holder_name": holder})
        return Response({"method": method, "number": number, "holder_name": holder})


class EarningsView(APIView):
    """GET /api/my/earnings/ : mes soldes, mes paiements reçus et mes reversements."""

    def get(self, request):
        from datetime import timedelta

        from apps.backoffice.config import cfg

        hold = timedelta(days=cfg().payout_hold_days)
        payments = Payment.objects.filter(payee=request.user, status__in=["paid", "refund_due", "refunded"]).order_by("-created_at")[:50]
        payouts = Payout.objects.filter(payee=request.user)[:20]
        account = PayoutAccount.objects.filter(user=request.user).first()
        return Response(
            {
                "balance": balance_for(request.user),
                "account": {"method": account.method, "number": account.number, "holder_name": account.holder_name} if account else None,
                "min_payout": cfg().min_payout_fcfa,
                "hold_days": cfg().payout_hold_days,
                "payments": [
                    {
                        "reference": p.reference, "purpose": p.purpose, "amount": p.amount, "fee": p.fee, "net": p.net, "commission_pct": p.commission_pct,
                        "status": p.status, "paid_at": p.paid_at, "available_at": (p.service_ends_at + hold) if p.service_ends_at else None, "in_payout": p.payout_id,
                    }
                    for p in payments
                ],
                "payouts": [{"id": o.id, "amount": o.amount, "status": o.status, "paid_at": o.paid_at, "created_at": o.created_at, "reference": o.reference} for o in payouts],
            }
        )
