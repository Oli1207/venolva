"""API d'administration (réservée au personnel). Chaque modification est écrite dans le journal d'audit."""
import csv
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, find_user
from apps.ambassadors.models import Contract as AmbassadorContract
from apps.gyms.models import Gym
from apps.market.models import Listing, Report
from apps.payments.models import Payment, Payout, WebhookEvent
from apps.payments.services import (
    PaymentRefused, PayoutError, accept_review, balance_for, cancel_payout, create_payout, eligible_payments, mark_payout_paid, mark_refunded,
)
from apps.notifications.services import notify
from apps.pros.models import ProProfile

from .models import GROUPS, SCHEMA, SCHEMA_BY_KEY, AuditLog, CommissionOverride, PlatformSettings, audit


class IsStaff(BasePermission):
    message = "Réservé à l'équipe Venolva."

    def has_permission(self, request, view):
        u = request.user
        return bool(u.is_authenticated and u.is_active and u.is_staff)


class AdminView(APIView):
    permission_classes = [IsStaff]


def page(request, qs, row):
    paginator = PageNumberPagination()
    paginator.page_size = 25
    items = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response([row(x) for x in items])


def person(u):
    return {"id": u.id, "name": u.display_name or u.email or u.phone, "email": u.email, "phone": u.phone, "initials": u.initials} if u else None


def bad(detail, code=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": detail}, status=code)


# --- Tableau de bord ---------------------------------------------------------------------------------------------------


class DashboardView(AdminView):
    def get(self, request):
        now = timezone.now()
        month = now - timedelta(days=30)
        paid = Payment.objects.filter(status="paid", paid_at__gte=month)
        agg = paid.aggregate(gross=Sum("amount"), fees=Sum("fee"), n=Count("id"))
        payees = User.objects.filter(earnings__isnull=False).distinct()
        available = sum(eligible_payments(u).aggregate(s=Sum("net"))["s"] or 0 for u in payees)
        refunds = Payment.objects.filter(status__in=["refund_due", "duplicate"]).aggregate(n=Count("id"), s=Sum("amount"))
        values = SettingsView.values()
        return Response(
            {
                "users": User.objects.count(),
                "new_users_7d": User.objects.filter(date_joined__gte=now - timedelta(days=7)).count(),
                "pros_pending": ProProfile.objects.filter(status="pending").count(),
                "listings_active": Listing.objects.filter(status="active").count(),
                "reports_open": Report.objects.filter(handled=False).count(),
                "payments_30d": {"count": agg["n"] or 0, "gross": agg["gross"] or 0, "fees": agg["fees"] or 0},
                "payouts": {
                    "available": available,
                    "pending": Payout.objects.filter(status="pending").aggregate(s=Sum("amount"))["s"] or 0,
                    "paid_total": Payout.objects.filter(status="paid").aggregate(s=Sum("amount"))["s"] or 0,
                },
                "refunds": {"count": refunds["n"] or 0, "amount": refunds["s"] or 0},
                "to_review": Payment.objects.filter(status="review").count(),
                "ambassador_contracts_ending": AmbassadorContract.objects.filter(
                    signed_at__isnull=False, terminated_at__isnull=True, renewals__isnull=True,
                    end_date__gte=timezone.localdate(), end_date__lte=timezone.localdate() + timedelta(days=30),
                ).count(),
                "commission_set": values["commission_booking_pct"] > 0 or values["commission_class_pct"] > 0,
            }
        )


# --- Réglages ------------------------------------------------------------------------------------------------------------


class SettingsView(AdminView):
    @staticmethod
    def values() -> dict:
        s = PlatformSettings.load()
        return {item["key"]: getattr(s, item["key"]) for item in SCHEMA}

    def payload(self):
        s = PlatformSettings.load()
        return {
            "groups": [{"key": k, "label": l} for k, l in GROUPS],
            "schema": SCHEMA,
            "values": self.values(),
            "updated_at": s.updated_at,
            "updated_by": person(s.updated_by),
        }

    def get(self, request):
        return Response(self.payload())

    def patch(self, request):
        incoming = request.data.get("values") if isinstance(request.data, dict) else None
        if not isinstance(incoming, dict) or not incoming:
            return bad("Aucune modification reçue.")
        errors = {}
        clean = {}
        for key, raw in incoming.items():
            meta = SCHEMA_BY_KEY.get(key)
            if meta is None:
                errors[key] = "Réglage inconnu."
                continue
            if meta.get("type") == "choice":
                if raw not in [c["value"] for c in meta["choices"]]:
                    errors[key] = "Valeur non proposée."
                else:
                    clean[key] = raw
                continue
            if isinstance(raw, bool) or not isinstance(raw, int):
                errors[key] = "Un nombre entier est attendu."
            elif not meta["min"] <= raw <= meta["max"]:
                errors[key] = f"Entre {meta['min']} et {meta['max']}."
            else:
                clean[key] = raw
        current = self.values()
        merged = {**current, **clean}
        if "price_min_fcfa" not in errors and "price_max_fcfa" not in errors and merged["price_min_fcfa"] >= merged["price_max_fcfa"]:
            errors["price_min_fcfa"] = "Le prix minimum doit rester inférieur au prix maximum."
        if errors:
            return Response({"detail": "Certains réglages sont invalides.", "errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        changes = {k: [current[k], v] for k, v in clean.items() if current[k] != v}
        if changes:
            s = PlatformSettings.load()
            for k, v in clean.items():
                setattr(s, k, v)
            s.updated_by = request.user
            s.save()
            audit(request.user, "settings.update", "PlatformSettings", changes=changes)
        return Response(self.payload())


class AuditView(AdminView):
    def get(self, request):
        qs = AuditLog.objects.select_related("actor")
        if request.query_params.get("action"):
            qs = qs.filter(action__startswith=request.query_params["action"])
        return page(request, qs, lambda a: {"id": a.id, "actor": person(a.actor), "action": a.action, "target": a.target, "detail": a.detail, "created_at": a.created_at})


# --- Commissions par vendeur ---------------------------------------------------------------------------------------------


def override_row(o):
    return {"id": o.id, "user": person(o.user), "purpose": o.purpose, "pct": o.pct, "note": o.note, "created_at": o.created_at}


class CommissionsView(AdminView):
    def get(self, request):
        return Response([override_row(o) for o in CommissionOverride.objects.select_related("user")])

    def post(self, request):
        try:
            user = find_user(request.data.get("email") or request.data.get("phone"))
        except (DjangoValidationError, User.DoesNotExist):
            return bad("Aucun compte avec cette adresse e-mail.")
        purpose, pct = request.data.get("purpose", "all"), request.data.get("pct")
        if purpose not in dict(CommissionOverride.Purpose.choices):
            return bad("Type de paiement inconnu.")
        if isinstance(pct, bool) or not isinstance(pct, int) or not 0 <= pct <= 50:
            return bad("Le taux doit être un entier entre 0 et 50.")
        obj, _ = CommissionOverride.objects.update_or_create(
            user=user, purpose=purpose, defaults={"pct": pct, "note": str(request.data.get("note", ""))[:120]}
        )
        audit(request.user, "commission.set", f"user:{user.id}", purpose=purpose, pct=pct)
        return Response(override_row(obj), status=status.HTTP_201_CREATED)


class CommissionDetailView(AdminView):
    def delete(self, request, pk):
        obj = get_object_or_404(CommissionOverride, pk=pk)
        audit(request.user, "commission.delete", f"user:{obj.user_id}", purpose=obj.purpose, pct=obj.pct)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Paiements ---------------------------------------------------------------------------------------------------------


def payment_row(p):
    return {
        "id": p.id, "reference": p.reference, "payer": person(p.user), "payee": person(p.payee), "purpose": p.purpose,
        "amount": p.amount, "fee": p.fee, "net": p.net, "commission_pct": p.commission_pct, "provider": p.provider,
        "method": p.method, "status": p.status, "created_at": p.created_at, "paid_at": p.paid_at, "payout": p.payout_id,
        "refunded_at": p.refunded_at, "refund_reference": p.refund_reference,
    }


class PaymentsView(AdminView):
    def get(self, request):
        qs = Payment.objects.select_related("user", "payee")
        p = request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("provider"):
            qs = qs.filter(provider=p["provider"])
        if p.get("q"):
            qs = qs.filter(Q(reference__icontains=p["q"]) | Q(user__phone__icontains=p["q"]) | Q(user__email__icontains=p["q"]) | Q(user__display_name__icontains=p["q"]))
        return page(request, qs, payment_row)


class PaymentActionView(AdminView):
    """POST /api/admin/payments/<id>/refund/ {reference} : le remboursement a été fait chez le prestataire.
    POST .../accept/ : valide comme payé un montant inattendu, après vérification."""

    def post(self, request, pk, action):
        payment = get_object_or_404(Payment, pk=pk)
        try:
            if action == "refund":
                mark_refunded(payment, str(request.data.get("reference", "")))
                audit(request.user, "payment.refund", payment.reference, amount=payment.amount, reference=payment.refund_reference)
            elif action == "accept":
                accept_review(payment)
                audit(request.user, "payment.accept", payment.reference, amount=payment.amount)
            else:
                return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        except PaymentRefused as exc:
            return bad(str(exc))
        return Response(payment_row(payment))


class WebhooksView(AdminView):
    def get(self, request):
        qs = WebhookEvent.objects.all()
        return page(request, qs, lambda w: {"id": w.id, "provider": w.provider, "event": w.event, "reference": w.reference, "outcome": w.outcome, "signature_valid": w.signature_valid, "detail": w.detail, "created_at": w.created_at})


# --- Reversements ----------------------------------------------------------------------------------------------------------


def payout_row(po, with_payments=False):
    row = {
        "id": po.id, "payee": person(po.payee), "amount": po.amount, "status": po.status, "method": po.method, "number": po.number,
        "holder_name": po.holder_name, "reference": po.reference, "created_at": po.created_at, "paid_at": po.paid_at,
        "created_by": person(po.created_by),
    }
    if with_payments:
        row["payments"] = [{"reference": p.reference, "net": p.net, "amount": p.amount, "fee": p.fee} for p in po.payments.all()]
    return row


class PayeesView(AdminView):
    """Qui a gagné de l'argent, et combien est disponible à reverser."""

    def get(self, request):
        users = User.objects.filter(earnings__isnull=False).distinct().select_related("payout_account")
        rows = []
        for u in users:
            b = balance_for(u)
            acct = getattr(u, "payout_account", None)
            rows.append({
                "user": person(u), "pro_type": u.pro_type, **b,
                "account": {"method": acct.method, "number": acct.number, "holder_name": acct.holder_name} if acct else None,
            })
        rows.sort(key=lambda r: r["available"], reverse=True)
        if request.query_params.get("available") == "1":
            rows = [r for r in rows if r["available"] > 0]
        return Response(rows)


class PayoutsView(AdminView):
    def get(self, request):
        qs = Payout.objects.select_related("payee", "created_by")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return page(request, qs, payout_row)

    def post(self, request):
        payee = User.objects.filter(pk=request.data.get("payee")).first()
        if payee is None:
            return bad("Bénéficiaire introuvable.")
        try:
            payout = create_payout(payee, request.user)
        except PayoutError as exc:
            return bad(str(exc))
        audit(request.user, "payout.create", f"payout:{payout.id}", payee=payee.id, amount=payout.amount)
        return Response(payout_row(payout, True), status=status.HTTP_201_CREATED)


class PayoutDetailView(AdminView):
    def get(self, request, pk):
        return Response(payout_row(get_object_or_404(Payout.objects.prefetch_related("payments"), pk=pk), True))


class PayoutActionView(AdminView):
    def post(self, request, pk, action):
        payout = get_object_or_404(Payout, pk=pk)
        try:
            if action == "paid":
                mark_payout_paid(payout, str(request.data.get("reference", "")))
                audit(request.user, "payout.paid", f"payout:{payout.id}", amount=payout.amount, reference=payout.reference)
            elif action == "cancel":
                cancel_payout(payout)
                audit(request.user, "payout.cancel", f"payout:{payout.id}", amount=payout.amount)
            else:
                return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        except PayoutError as exc:
            return bad(str(exc))
        return Response(payout_row(payout, True))


def safe_cell(value):
    """Un tableur exécuterait une cellule commençant par = + - @ : on la neutralise."""
    text = str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


class PayoutsExportView(AdminView):
    """GET /api/admin/payouts/export/?status=pending : fichier CSV pour faire les virements en lot."""

    def get(self, request):
        qs = Payout.objects.select_related("payee")
        qs = qs.filter(status=request.query_params.get("status", "pending"))
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="reversements.csv"'
        response.write("﻿")  # accents corrects dans Excel
        w = csv.writer(response, delimiter=";")
        w.writerow(["Reversement", "Bénéficiaire", "Moyen", "Numéro", "Titulaire", "Montant FCFA", "Statut", "Référence"])
        for po in qs:
            w.writerow([po.id, safe_cell(po.payee.display_name or po.payee.email or po.payee.phone), po.method, po.number, safe_cell(po.holder_name), po.amount, po.status, safe_cell(po.reference)])
        return response


# --- Dossiers pro ------------------------------------------------------------------------------------------------------------


def application_row(p):
    return {
        "id": p.id, "user": person(p.user), "pro_type": p.user.pro_type, "speciality": p.speciality, "bio": p.bio, "credential": p.credential,
        "years_experience": p.years_experience, "gym": p.gym.name if p.gym_id else None, "status": p.status, "review_note": p.review_note, "created_at": p.created_at,
    }


class ProApplicationsView(AdminView):
    def get(self, request):
        qs = ProProfile.objects.select_related("user", "gym").order_by("created_at")
        st = request.query_params.get("status", "pending")
        if st != "all":
            qs = qs.filter(status=st)
        return page(request, qs, application_row)


class ProApplicationActionView(AdminView):
    def post(self, request, pk, action):
        p = get_object_or_404(ProProfile.objects.select_related("user", "gym"), pk=pk)
        if action == "approve":
            p.approve()
            audit(request.user, "pro.approve", f"user:{p.user_id}", pro_type=p.user.pro_type)
            notify(p.user, "pro_approved", "Ton compte pro est validé", "Tu as la coche verte.", "/pro")
        elif action == "reject":
            p.reject(str(request.data.get("note", "")))
            audit(request.user, "pro.reject", f"user:{p.user_id}", note=p.review_note)
            notify(p.user, "pro_rejected", "Ton dossier pro n'a pas été validé", p.review_note, "/pro/devenir")
        else:
            return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        return Response(application_row(p))


# --- Salles --------------------------------------------------------------------------------------------------------------------


def gym_row(g):
    return {"id": g.id, "name": g.name, "commune": g.commune, "address": g.address, "verified": g.verified, "owner": person(g.owner)}


class GymsView(AdminView):
    def get(self, request):
        qs = Gym.objects.select_related("owner")
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(commune__icontains=q))
        return page(request, qs, gym_row)


class GymDetailView(AdminView):
    """PATCH {verified?, owner_phone?} : valider une salle, ou la rattacher à son gérant (vide pour détacher)."""

    def patch(self, request, pk):
        gym = get_object_or_404(Gym, pk=pk)
        changes = {}
        if "verified" in request.data:
            if not isinstance(request.data["verified"], bool):
                return bad("« verified » doit être vrai ou faux.")
            changes["verified"] = [gym.verified, request.data["verified"]]
            gym.verified = request.data["verified"]
        if "owner_phone" in request.data:
            raw = str(request.data["owner_phone"] or "").strip()
            if raw:
                try:
                    owner = find_user(raw)
                except (DjangoValidationError, User.DoesNotExist):
                    return bad("Aucun compte avec cette adresse e-mail.")
            else:
                owner = None
            changes["owner"] = [gym.owner_id, owner.id if owner else None]
            gym.owner = owner
        gym.save()
        audit(request.user, "gym.update", f"gym:{gym.id}", changes=changes)
        return Response(gym_row(gym))


# --- Modération du marché ----------------------------------------------------------------------------------------------------------


def report_row(r):
    l = r.listing
    return {
        "id": r.id, "reason": r.reason, "detail": r.detail, "handled": r.handled, "created_at": r.created_at, "reporter": person(r.reporter),
        "listing": {"id": l.id, "title": l.title, "price": l.price, "status": l.status, "seller": person(l.seller)},
        "reports_on_listing": l.reports.count(),
    }


class ReportsView(AdminView):
    def get(self, request):
        qs = Report.objects.select_related("listing", "listing__seller", "reporter")
        if request.query_params.get("handled") != "all":
            qs = qs.filter(handled=request.query_params.get("handled") == "1")
        return page(request, qs, report_row)


class ReportActionView(AdminView):
    def post(self, request, pk, action):
        r = get_object_or_404(Report.objects.select_related("listing", "listing__seller", "reporter"), pk=pk)
        if action == "hide":
            r.listing.status = Listing.Status.HIDDEN
            r.listing.save(update_fields=["status"])
            Report.objects.filter(listing=r.listing).update(handled=True)
            audit(request.user, "report.hide", f"listing:{r.listing_id}", title=r.listing.title)
        elif action == "dismiss":
            r.handled = True
            r.save(update_fields=["handled"])
            audit(request.user, "report.dismiss", f"listing:{r.listing_id}")
        else:
            return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        r.refresh_from_db()
        return Response(report_row(r))


# --- Utilisateurs --------------------------------------------------------------------------------------------------------------------


def user_row(u):
    return {**person(u), "commune": u.commune, "is_active": u.is_active, "is_staff": u.is_staff, "pro_type": u.pro_type, "pro_verified": u.pro_verified, "date_joined": u.date_joined}


class UsersView(AdminView):
    def get(self, request):
        qs = User.objects.order_by("-date_joined")
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(Q(phone__icontains=q) | Q(email__icontains=q) | Q(display_name__icontains=q))
        if request.query_params.get("staff") == "1":
            qs = qs.filter(is_staff=True)
        return page(request, qs, user_row)


class UserDetailView(AdminView):
    """PATCH {is_active?, is_staff?} : suspendre un compte, ou donner l'accès à l'administration (superutilisateur seulement)."""

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return bad("Tu ne peux pas modifier ton propre compte ici.")
        if user.is_superuser:
            return bad("Un superutilisateur ne se modifie pas ici.", status.HTTP_403_FORBIDDEN)
        changes = {}
        for field in ("is_active", "is_staff"):
            if field in request.data:
                value = request.data[field]
                if not isinstance(value, bool):
                    return bad(f"« {field} » doit être vrai ou faux.")
                if field == "is_staff" and not request.user.is_superuser:
                    return bad("Seul un superutilisateur peut donner l'accès à l'administration.", status.HTTP_403_FORBIDDEN)
                changes[field] = [getattr(user, field), value]
                setattr(user, field, value)
        user.save()
        audit(request.user, "user.update", f"user:{user.id}", changes=changes)
        return Response(user_row(user))
