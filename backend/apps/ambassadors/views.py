"""API des ambassadeurs : administration (équipe) et espace de l'ambassadeur."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, find_user
from apps.backoffice.models import audit
from apps.backoffice.views import AdminView, bad, person
from apps.payments.models import PayoutAccount

from .models import Ambassador, Contract, Statement
from .services import (
    AmbassadorError, cancel_statement, create_contract, current_contract, generate_statement, mark_paid, month_bounds, preview, renew_contract,
    sign_contract, terminate_contract, totals,
)


def parse_date(raw, field="date"):
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise AmbassadorError(f"{field} invalide (AAAA-MM-JJ).")


def contract_row(c: Contract) -> dict:
    today = timezone.localdate()
    state = c.state(today)
    return {
        "id": c.id, "start_date": c.start_date, "end_date": c.end_date, "share_pct": c.share_pct, "state": state,
        "signed_at": c.signed_at, "terminated_at": c.terminated_at, "termination_note": c.termination_note,
        "renewal_of": c.renewal_of_id, "renewed": c.renewals.filter(terminated_at__isnull=True).exists(),
        "days_left": (c.effective_end - today).days if state == "active" else None,
        "preview": preview(c) if state in ("active", "ended") else None,
    }


def statement_row(s: Statement) -> dict:
    return {
        "id": s.id, "contract": s.contract_id, "month": s.month, "fees_total": s.fees_total, "share_pct": s.share_pct, "amount": s.amount,
        "status": s.status, "reference": s.reference, "paid_at": s.paid_at, "payments": s.lines.count(),
    }


def account_row(user):
    a = PayoutAccount.objects.filter(user=user).first()
    return {"method": a.method, "number": a.number, "holder_name": a.holder_name} if a else None


def detail_payload(amb: Ambassador) -> dict:
    return {
        "id": amb.id, "user": person(amb.user), "notes": amb.notes, "account": account_row(amb.user), "totals": totals(amb),
        "contracts": [contract_row(c) for c in amb.contracts.all()],
        "statements": [statement_row(s) for s in Statement.objects.filter(contract__ambassador=amb).select_related("contract")],
    }


# --- Administration ---------------------------------------------------------------------------------------------------------


class AmbassadorsView(AdminView):
    def get(self, request):
        rows = []
        for amb in Ambassador.objects.select_related("user"):
            c = current_contract(amb)
            rows.append({
                "id": amb.id, "user": person(amb.user), "contract": contract_row(c) if c else None, "totals": totals(amb),
                "ending_soon": bool(c and c.state() == "active" and (c.effective_end - timezone.localdate()).days <= 30),
            })
        return Response(rows)

    def post(self, request):
        try:
            user = find_user(request.data.get("email") or request.data.get("phone"))
        except (DjangoValidationError, User.DoesNotExist):
            return bad("Aucun compte avec cette adresse e-mail. La personne doit d'abord se connecter une fois à l'app.")
        if Ambassador.objects.filter(user=user).exists():
            return bad("Cette personne est déjà ambassadrice.")
        amb = Ambassador.objects.create(user=user, notes=str(request.data.get("notes", ""))[:300])
        audit(request.user, "ambassador.create", f"user:{user.id}")
        return Response(detail_payload(amb), status=status.HTTP_201_CREATED)


class AmbassadorDetailView(AdminView):
    def get(self, request, pk):
        return Response(detail_payload(get_object_or_404(Ambassador.objects.select_related("user"), pk=pk)))


class ContractCreateView(AdminView):
    """POST {start_date, months?, share_pct?} : nouveau contrat en brouillon. Durée et taux viennent des réglages si omis."""

    def post(self, request, pk):
        amb = get_object_or_404(Ambassador, pk=pk)
        try:
            d = request.data
            for key in ("months", "share_pct"):
                if d.get(key) is not None and (isinstance(d[key], bool) or not isinstance(d[key], int)):
                    raise AmbassadorError("Un nombre entier est attendu.")
            c = create_contract(amb, start=parse_date(d.get("start_date"), "Date de début"), months=d.get("months"), share_pct=d.get("share_pct"), actor=request.user)
        except AmbassadorError as exc:
            return bad(str(exc))
        audit(request.user, "contract.create", f"ambassador:{amb.id}", start=str(c.start_date), end=str(c.end_date), share_pct=c.share_pct)
        return Response(detail_payload(amb), status=status.HTTP_201_CREATED)


class ContractActionView(AdminView):
    """POST /api/admin/contracts/<id>/sign|renew|terminate/"""

    def post(self, request, pk, action):
        c = get_object_or_404(Contract.objects.select_related("ambassador", "ambassador__user"), pk=pk)
        d = request.data
        try:
            if action == "sign":
                sign_contract(c, parse_date(d.get("signed_at") or timezone.localdate().isoformat(), "Date de signature"))
                audit(request.user, "contract.sign", f"contract:{c.id}", signed_at=str(c.signed_at))
            elif action == "renew":
                for key in ("months", "share_pct"):
                    if d.get(key) is not None and (isinstance(d[key], bool) or not isinstance(d[key], int)):
                        raise AmbassadorError("Un nombre entier est attendu.")
                new = renew_contract(c, months=d.get("months"), share_pct=d.get("share_pct"), actor=request.user)
                audit(request.user, "contract.renew", f"contract:{c.id}", new=new.id, start=str(new.start_date), end=str(new.end_date), share_pct=new.share_pct)
            elif action == "terminate":
                terminate_contract(c, parse_date(d.get("on") or timezone.localdate().isoformat(), "Date de fin"), str(d.get("note", "")))
                audit(request.user, "contract.terminate", f"contract:{c.id}", on=str(c.terminated_at), note=c.termination_note)
            else:
                return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        except AmbassadorError as exc:
            return bad(str(exc))
        return Response(detail_payload(c.ambassador))


class StatementCreateView(AdminView):
    """POST {contract, month: "2026-12"} : génère le relevé d'un mois terminé."""

    def post(self, request, pk):
        amb = get_object_or_404(Ambassador, pk=pk)
        contract = Contract.objects.filter(pk=request.data.get("contract"), ambassador=amb).first()
        if contract is None:
            return bad("Contrat introuvable.")
        try:
            month = parse_date(f"{str(request.data.get('month', ''))[:7]}-01", "Mois")
            st = generate_statement(contract, month, request.user)
        except AmbassadorError as exc:
            return bad(str(exc))
        audit(request.user, "statement.generate", f"statement:{st.id}", month=str(st.month), fees=st.fees_total, pct=st.share_pct, amount=st.amount)
        return Response(detail_payload(amb), status=status.HTTP_201_CREATED)


class StatementActionView(AdminView):
    def post(self, request, pk, action):
        st = get_object_or_404(Statement.objects.select_related("contract__ambassador"), pk=pk)
        try:
            if action == "paid":
                mark_paid(st, str(request.data.get("reference", "")))
                audit(request.user, "statement.paid", f"statement:{st.id}", amount=st.amount, reference=st.reference)
            elif action == "cancel":
                cancel_statement(st)
                audit(request.user, "statement.cancel", f"statement:{st.id}", amount=st.amount)
            else:
                return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        except AmbassadorError as exc:
            return bad(str(exc))
        return Response(detail_payload(st.contract.ambassador))


# --- Espace de l'ambassadeur --------------------------------------------------------------------------------------------------


class MyAmbassadorView(APIView):
    """GET /api/my/ambassador/ : mon contrat, ce que j'ai déjà gagné ce mois-ci, mes relevés."""

    def get(self, request):
        amb = Ambassador.objects.filter(user=request.user).first()
        if amb is None:
            return Response({"detail": "Tu n'es pas ambassadrice."}, status=status.HTTP_403_FORBIDDEN)
        c = current_contract(amb)
        data = detail_payload(amb)
        statements = [s for s in data["statements"] if s["status"] != "cancelled"]
        return Response({
            "contract": contract_row(c) if c else None,
            "contracts": data["contracts"], "statements": statements, "totals": data["totals"], "account": data["account"],
        })
