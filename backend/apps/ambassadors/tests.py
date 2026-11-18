"""Tests du volet ambassadeurs : durée des contrats, calcul des gains, relevés, droits d'accès."""
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.testing import client_for, make_member
from apps.backoffice.models import AuditLog
from apps.backoffice.tests import make_staff, paid_payment, set_cfg
from apps.payments.models import Payment
from apps.payments.services import balance_for

from .models import Ambassador, Contract, Statement, StatementLine
from .services import (
    AmbassadorError, add_months, cancel_statement, create_contract, current_contract, generate_statement, mark_paid, preview, renew_contract,
    sign_contract, term_end, terminate_contract, totals,
)

TODAY = timezone.localdate()
THIS_MONTH = TODAY.replace(day=1)
LAST_MONTH = (THIS_MONTH - timedelta(days=1)).replace(day=1)
TWO_MONTHS_AGO = (LAST_MONTH - timedelta(days=1)).replace(day=1)


def settled_in(month_first: date, day=10, net=None, amount=10000, fee=None):
    """Un paiement dont le service a eu lieu ce jour-là (le délai d'attente par défaut est de 2 jours)."""
    ends = timezone.make_aware(datetime.combine(month_first.replace(day=day), time(12)), timezone.get_current_timezone())
    p = paid_payment(make_member("Pro"), net=amount - (fee if fee is not None else amount // 10), amount=amount)
    Payment.objects.filter(pk=p.pk).update(service_ends_at=ends)
    p.refresh_from_db()
    return p


def make_ambassador(name="Amie"):
    return Ambassador.objects.create(user=make_member(name))


def signed_contract(amb, start=None, months=6, pct=20):
    c = create_contract(amb, start=start or TWO_MONTHS_AGO, months=months, share_pct=pct)
    sign_contract(c, TODAY)
    return c


class DateMathTests(APITestCase):
    def test_add_months_keeps_a_valid_day(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.assertEqual(add_months(date(2026, 11, 15), 3), date(2027, 2, 15))
        self.assertEqual(add_months(date(2026, 12, 1), 12), date(2027, 12, 1))

    def test_a_six_month_term_ends_the_day_before_the_anniversary(self):
        self.assertEqual(term_end(date(2026, 12, 1), 6), date(2027, 5, 31))
        self.assertEqual(term_end(date(2026, 1, 1), 6), date(2026, 6, 30))
        self.assertEqual(term_end(date(2026, 8, 31), 6), date(2027, 2, 27))  # pas de 31 février


class ContractTests(APITestCase):
    def setUp(self):
        self.amb = make_ambassador()

    def test_defaults_come_from_the_settings(self):
        set_cfg(ambassador_share_pct=15, ambassador_contract_months=6)
        c = create_contract(self.amb, start=date(2026, 12, 1))
        self.assertEqual((c.share_pct, c.end_date), (15, date(2027, 5, 31)))
        self.assertIsNone(c.signed_at)

    def test_invalid_terms_are_refused(self):
        with self.assertRaises(AmbassadorError):
            create_contract(self.amb, start=date(2026, 12, 1), months=0)
        with self.assertRaises(AmbassadorError):
            create_contract(self.amb, start=date(2026, 12, 1), months=37)
        with self.assertRaises(AmbassadorError):
            create_contract(self.amb, start=date(2026, 12, 1), share_pct=101)

    def test_overlapping_contracts_are_refused_but_a_terminated_one_frees_the_dates(self):
        first = create_contract(self.amb, start=date(2026, 12, 1), share_pct=10)
        with self.assertRaises(AmbassadorError):
            create_contract(self.amb, start=date(2027, 3, 1), share_pct=10)
        create_contract(self.amb, start=date(2027, 6, 1), share_pct=10)  # le lendemain de la fin : accepté
        terminate_contract(first, date(2026, 12, 31), "Fin anticipée")
        create_contract(self.amb, start=date(2027, 3, 1), months=3, share_pct=10)  # libre : le premier s'est arrêté fin décembre
        with self.assertRaises(AmbassadorError):  # mais pendant sa durée réelle, c'est toujours occupé
            create_contract(self.amb, start=date(2026, 12, 15), months=1, share_pct=10)

    def test_state_machine(self):
        c = create_contract(self.amb, start=TODAY - timedelta(days=10), months=6, share_pct=10)
        self.assertEqual(c.state(), "draft")
        sign_contract(c, TODAY)
        self.assertEqual(c.state(), "active")
        self.assertEqual(c.state(TODAY - timedelta(days=30)), "upcoming")
        self.assertEqual(c.state(c.end_date + timedelta(days=1)), "ended")
        terminate_contract(c, TODAY, "Fin d'un commun accord")
        self.assertEqual(c.state(), "terminated")
        self.assertEqual(c.effective_end, TODAY)

    def test_sign_and_terminate_only_once(self):
        c = create_contract(self.amb, start=TODAY, share_pct=10)
        sign_contract(c, TODAY)
        with self.assertRaises(AmbassadorError):
            sign_contract(c, TODAY)
        terminate_contract(c, TODAY, "x")
        with self.assertRaises(AmbassadorError):
            terminate_contract(c, TODAY, "x")
        with self.assertRaises(AmbassadorError):
            sign_contract(c, TODAY)

    def test_renewal_starts_the_next_day_with_the_same_terms(self):
        c = signed_contract(self.amb, start=date(2026, 12, 1), months=6, pct=18)
        new = renew_contract(c)
        self.assertEqual((new.start_date, new.end_date, new.share_pct, new.renewal_of), (date(2027, 6, 1), date(2027, 11, 30), 18, c))
        self.assertIsNone(new.signed_at)  # il faut le signer : pas de reconduction silencieuse
        with self.assertRaisesRegex(AmbassadorError, "déjà"):
            renew_contract(c)

    def test_renewal_can_change_the_terms(self):
        c = signed_contract(self.amb, start=date(2026, 12, 1), months=6, pct=18)
        new = renew_contract(c, months=3, share_pct=25)
        self.assertEqual((new.share_pct, new.end_date), (25, date(2027, 8, 31)))

    def test_a_terminated_contract_cannot_be_renewed(self):
        c = signed_contract(self.amb)
        terminate_contract(c, TODAY, "x")
        with self.assertRaises(AmbassadorError):
            renew_contract(c)

    def test_current_contract_prefers_the_running_one(self):
        old = signed_contract(self.amb, start=TODAY - timedelta(days=400), months=6)
        running = signed_contract(self.amb, start=TODAY - timedelta(days=30), months=6)
        self.assertEqual(current_contract(self.amb), running)
        self.assertNotEqual(current_contract(self.amb), old)


class EarningsTests(APITestCase):
    def setUp(self):
        self.amb = make_ambassador()
        self.c = signed_contract(self.amb, start=TWO_MONTHS_AGO, pct=20)

    def test_unsigned_contract_earns_nothing(self):
        other = make_ambassador("Autre")
        draft = create_contract(other, start=TWO_MONTHS_AGO, share_pct=50)
        settled_in(LAST_MONTH)
        self.assertEqual(preview(draft), {"fees": 0, "amount": 0, "payments": 0})
        with self.assertRaisesRegex(AmbassadorError, "signé"):
            generate_statement(draft, LAST_MONTH)

    def test_only_commissions_count_and_the_share_is_applied(self):
        settled_in(LAST_MONTH, amount=10000, fee=1000)
        settled_in(LAST_MONTH, day=15, amount=20000, fee=2000)
        st = generate_statement(self.c, LAST_MONTH)
        self.assertEqual((st.fees_total, st.share_pct, st.amount, st.status), (3000, 20, 600, "pending"))  # 20 % de 3 000 F, pas de 30 000 F
        self.assertEqual(st.lines.count(), 2)

    def test_amount_is_rounded_to_the_nearest_franc(self):
        settled_in(LAST_MONTH, fee=3333, amount=33330)
        self.assertEqual(generate_statement(self.c, LAST_MONTH).amount, 667)  # 666,6

    def test_zero_commission_means_zero_earnings(self):
        settled_in(LAST_MONTH, fee=0, amount=10000)
        st = generate_statement(self.c, LAST_MONTH)
        self.assertEqual((st.fees_total, st.amount), (0, 0))

    def test_recent_services_are_not_yet_earned(self):
        # service hier : avec 2 jours d'attente, la commission n'est pas encore acquise
        p = settled_in(THIS_MONTH)
        Payment.objects.filter(pk=p.pk).update(service_ends_at=timezone.now() - timedelta(days=1))
        self.assertEqual(preview(self.c)["fees"], 0)
        set_cfg(payout_hold_days=0)
        self.assertEqual(preview(self.c)["fees"], p.fee)

    def test_refunded_unpaid_and_duplicate_payments_never_count(self):
        settled_in(LAST_MONTH, fee=1000)
        for status in ("refund_due", "refunded", "pending", "review", "duplicate", "failed"):
            p = settled_in(LAST_MONTH, day=12, fee=5000, amount=50000)
            Payment.objects.filter(pk=p.pk).update(status=status)
        st = generate_statement(self.c, LAST_MONTH)
        self.assertEqual(st.fees_total, 1000)

    def test_payments_outside_the_contract_dates_do_not_count(self):
        before = settled_in(TWO_MONTHS_AGO - timedelta(days=40))  # réglé avant le début du contrat
        inside = settled_in(LAST_MONTH)
        st = generate_statement(self.c, LAST_MONTH)
        self.assertEqual(set(st.lines.values_list("payment_id", flat=True)), {inside.pk})
        self.assertFalse(StatementLine.objects.filter(payment=before).exists())

    def test_a_termination_stops_the_earnings(self):
        settled_in(LAST_MONTH, day=5, fee=1000)
        late = settled_in(LAST_MONTH, day=25, fee=4000, amount=40000)
        terminate_contract(self.c, LAST_MONTH.replace(day=15), "Résiliation")
        st = generate_statement(self.c, LAST_MONTH)
        self.assertEqual(st.fees_total, 1000)
        self.assertFalse(StatementLine.objects.filter(payment=late).exists())

    def test_the_current_month_cannot_be_closed_yet(self):
        with self.assertRaisesRegex(AmbassadorError, "pas terminé"):
            generate_statement(self.c, THIS_MONTH)

    def test_months_outside_the_contract_are_refused(self):
        with self.assertRaisesRegex(AmbassadorError, "en dehors"):
            generate_statement(self.c, TWO_MONTHS_AGO - timedelta(days=100))

    def test_one_statement_per_month(self):
        settled_in(LAST_MONTH)
        generate_statement(self.c, LAST_MONTH)
        with self.assertRaisesRegex(AmbassadorError, "existe déjà"):
            generate_statement(self.c, LAST_MONTH)

    def test_a_payment_is_never_counted_twice(self):
        old = settled_in(TWO_MONTHS_AGO, day=20)
        last = settled_in(LAST_MONTH)
        first = generate_statement(self.c, LAST_MONTH)  # on a sauté le mois d'avant : le rattrapage est inclus
        self.assertEqual(set(first.lines.values_list("payment_id", flat=True)), {old.pk, last.pk})
        with self.assertRaises(IntegrityError), transaction.atomic():
            StatementLine.objects.create(statement=first, payment=old, fee=old.fee)  # contrainte en base
        self.assertEqual(preview(self.c)["fees"], 0)

    def test_cancelling_a_statement_releases_its_payments(self):
        p = settled_in(LAST_MONTH)
        st = generate_statement(self.c, LAST_MONTH)
        cancel_statement(st)
        self.assertEqual((st.status, st.lines.count()), ("cancelled", 0))
        again = generate_statement(self.c, LAST_MONTH)  # on peut le refaire
        self.assertEqual(set(again.lines.values_list("payment_id", flat=True)), {p.pk})

    def test_paying_needs_a_reference_and_is_final(self):
        settled_in(LAST_MONTH)
        st = generate_statement(self.c, LAST_MONTH)
        with self.assertRaisesRegex(AmbassadorError, "référence"):
            mark_paid(st, " ")
        mark_paid(st, "WAVE-77")
        st.refresh_from_db()
        self.assertEqual((st.status, st.reference), ("paid", "WAVE-77"))
        self.assertIsNotNone(st.paid_at)
        with self.assertRaises(AmbassadorError):
            mark_paid(st, "AUTRE")
        with self.assertRaises(AmbassadorError):
            cancel_statement(st)

    def test_totals(self):
        settled_in(LAST_MONTH, fee=1000)
        st = generate_statement(self.c, LAST_MONTH)
        self.assertEqual(totals(self.amb), {"pending": 200, "paid": 0})
        mark_paid(st, "REF")
        self.assertEqual(totals(self.amb), {"pending": 0, "paid": 200})

    def test_the_rate_is_frozen_on_each_statement(self):
        settled_in(LAST_MONTH, fee=1000)
        st = generate_statement(self.c, LAST_MONTH)
        Contract.objects.filter(pk=self.c.pk).update(share_pct=90)
        st.refresh_from_db()
        self.assertEqual((st.share_pct, st.amount), (20, 200))

    def test_ambassador_earnings_do_not_touch_the_sellers_money(self):
        p = settled_in(LAST_MONTH, amount=10000, fee=1000)
        before = balance_for(p.payee)
        generate_statement(self.c, LAST_MONTH)
        self.assertEqual(balance_for(p.payee), before)
        p.refresh_from_db()
        self.assertEqual(p.net, 9000)


class AmbassadorApiTests(APITestCase):
    def setUp(self):
        self.admin = make_staff()
        self.friend = make_member("Amie d'Olivier")
        self.c = client_for(self.admin)

    def create_amb(self):
        res = self.c.post("/api/admin/ambassadors/", {"phone": self.friend.phone}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()["id"]

    def test_staff_only(self):
        member = client_for(make_member("Simple"))
        for method, url in (("get", "/api/admin/ambassadors/"), ("post", "/api/admin/ambassadors/"), ("get", "/api/admin/ambassadors/1/"), ("post", "/api/admin/contracts/1/sign/"), ("post", "/api/admin/statements/1/paid/")):
            self.assertEqual(getattr(member, method)(url).status_code, 403, url)
            self.assertEqual(getattr(APIClient(), method)(url).status_code, 401, url)

    def test_an_ambassador_cannot_use_the_admin_api(self):
        self.create_amb()
        self.assertEqual(client_for(self.friend).get("/api/admin/ambassadors/").status_code, 403)

    def test_creating_an_ambassador(self):
        self.create_amb()
        self.assertEqual(self.c.post("/api/admin/ambassadors/", {"phone": self.friend.phone}, format="json").status_code, 400)  # doublon
        self.assertEqual(self.c.post("/api/admin/ambassadors/", {"phone": "0799999999"}, format="json").status_code, 400)  # inconnue
        self.assertEqual(self.c.post("/api/admin/ambassadors/", {"phone": "n'importe quoi"}, format="json").status_code, 400)
        self.assertTrue(client_for(self.friend).get("/api/auth/me/").json()["is_ambassador"])
        self.assertFalse(client_for(self.admin).get("/api/auth/me/").json()["is_ambassador"])

    def test_full_lifecycle_through_the_api(self):
        set_cfg(ambassador_share_pct=20)
        amb = self.create_amb()
        start = TWO_MONTHS_AGO.isoformat()
        res = self.c.post(f"/api/admin/ambassadors/{amb}/contracts/", {"start_date": start}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        contract = res.json()["contracts"][0]
        self.assertEqual((contract["state"], contract["share_pct"]), ("draft", 20))
        self.assertEqual(self.c.post(f"/api/admin/ambassadors/{amb}/statements/", {"contract": contract["id"], "month": LAST_MONTH.isoformat()[:7]}, format="json").status_code, 400)  # pas signé

        signed = self.c.post(f"/api/admin/contracts/{contract['id']}/sign/", {}, format="json").json()
        self.assertEqual(signed["contracts"][0]["state"], "active")

        settled_in(LAST_MONTH, fee=1000)
        month = LAST_MONTH.isoformat()[:7]
        gen = self.c.post(f"/api/admin/ambassadors/{amb}/statements/", {"contract": contract["id"], "month": month}, format="json")
        self.assertEqual(gen.status_code, 201, gen.content)
        st = gen.json()["statements"][0]
        self.assertEqual((st["fees_total"], st["amount"], st["status"], st["payments"]), (1000, 200, "pending", 1))
        self.assertEqual(self.c.post(f"/api/admin/ambassadors/{amb}/statements/", {"contract": contract["id"], "month": month}, format="json").status_code, 400)

        self.assertEqual(self.c.post(f"/api/admin/statements/{st['id']}/paid/", {}, format="json").status_code, 400)
        paid = self.c.post(f"/api/admin/statements/{st['id']}/paid/", {"reference": "WAVE-1"}, format="json").json()
        self.assertEqual((paid["statements"][0]["status"], paid["totals"]), ("paid", {"pending": 0, "paid": 200}))

        renewed = self.c.post(f"/api/admin/contracts/{contract['id']}/renew/", {"share_pct": 25}, format="json").json()
        self.assertEqual(len(renewed["contracts"]), 2)
        self.assertEqual(self.c.post(f"/api/admin/contracts/{contract['id']}/renew/", {}, format="json").status_code, 400)

        actions = list(AuditLog.objects.order_by("id").values_list("action", flat=True))
        self.assertEqual(actions, ["ambassador.create", "contract.create", "contract.sign", "statement.generate", "statement.paid", "contract.renew"])

    def test_contract_input_validation(self):
        amb = self.create_amb()
        url = f"/api/admin/ambassadors/{amb}/contracts/"
        self.assertEqual(self.c.post(url, {}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {"start_date": "demain"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {"start_date": "2026-12-01", "share_pct": "20"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {"start_date": "2026-12-01", "share_pct": 150}, format="json").status_code, 400)
        self.assertEqual(self.c.post(url, {"start_date": "2026-12-01", "months": True}, format="json").status_code, 400)

    def test_terminating_through_the_api_keeps_a_trace(self):
        amb = self.create_amb()
        cid = self.c.post(f"/api/admin/ambassadors/{amb}/contracts/", {"start_date": TODAY.isoformat(), "share_pct": 10}, format="json").json()["contracts"][0]["id"]
        self.c.post(f"/api/admin/contracts/{cid}/sign/", {}, format="json")
        res = self.c.post(f"/api/admin/contracts/{cid}/terminate/", {"note": "Fin d'un commun accord"}, format="json").json()["contracts"][0]
        self.assertEqual((res["state"], res["termination_note"]), ("terminated", "Fin d'un commun accord"))
        self.assertEqual(self.c.post(f"/api/admin/contracts/{cid}/zzz/").status_code, 404)

    def test_list_flags_contracts_ending_soon(self):
        amb = Ambassador.objects.create(user=self.friend)
        c = create_contract(amb, start=TODAY - timedelta(days=170), months=6, share_pct=10)
        sign_contract(c, TODAY)
        row = self.c.get("/api/admin/ambassadors/").json()[0]
        self.assertTrue(row["ending_soon"])
        self.assertEqual(row["contract"]["state"], "active")

    def test_my_space_shows_only_my_own_data(self):
        amb = make_ambassador("Autre ambassadrice")
        other_contract = signed_contract(amb, pct=50)
        settled_in(LAST_MONTH, fee=1000)
        generate_statement(other_contract, LAST_MONTH)

        mine = Ambassador.objects.create(user=self.friend)
        c = signed_contract(mine, pct=20)
        body = client_for(self.friend).get("/api/my/ambassador/").json()
        self.assertEqual((body["contract"]["id"], body["contract"]["share_pct"], body["statements"], body["totals"]), (c.id, 20, [], {"pending": 0, "paid": 0}))
        self.assertEqual(len(body["contracts"]), 1)

    def test_my_space_shows_the_running_estimate_and_hides_cancelled_statements(self):
        mine = Ambassador.objects.create(user=self.friend)
        c = signed_contract(mine, pct=20)
        settled_in(LAST_MONTH, fee=1000)
        st = generate_statement(c, LAST_MONTH)
        settled_in(LAST_MONTH, day=20, fee=500, amount=5000)
        # un paiement réglé après la fin du mois dernier mais avant aujourd'hui compte dans l'estimation
        p = settled_in(THIS_MONTH.replace(day=1), fee=700, amount=7000)
        Payment.objects.filter(pk=p.pk).update(service_ends_at=timezone.now() - timedelta(days=5))
        body = client_for(self.friend).get("/api/my/ambassador/").json()
        self.assertEqual(body["contract"]["preview"]["amount"], round((500 + 700) * 0.2))
        cancel_statement(st)
        self.assertEqual(client_for(self.friend).get("/api/my/ambassador/").json()["statements"], [])

    def test_non_ambassadors_get_a_403(self):
        self.assertEqual(client_for(make_member("Simple")).get("/api/my/ambassador/").status_code, 403)
        self.assertEqual(APIClient().get("/api/my/ambassador/").status_code, 401)

    def test_her_payout_account_is_visible_to_the_team(self):
        from apps.payments.models import PayoutAccount

        amb = self.create_amb()
        self.assertIsNone(self.c.get(f"/api/admin/ambassadors/{amb}/").json()["account"])
        client_for(self.friend).put("/api/my/payout-account/", {"method": "wave", "number": "07 00 00 01 01", "holder_name": "Amie K."}, format="json")
        self.assertEqual(self.c.get(f"/api/admin/ambassadors/{amb}/").json()["account"]["holder_name"], "Amie K.")
        self.assertEqual(PayoutAccount.objects.count(), 1)

    def test_settings_expose_the_ambassador_defaults(self):
        body = self.c.get("/api/admin/settings/").json()
        self.assertIn("ambassadors", [g["key"] for g in body["groups"]])
        self.assertEqual((body["values"]["ambassador_share_pct"], body["values"]["ambassador_contract_months"]), (0, 6))
        bad = self.c.patch("/api/admin/settings/", {"values": {"ambassador_share_pct": 101}}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.c.patch("/api/admin/settings/", {"values": {"ambassador_share_pct": 20}}, format="json")
        self.assertEqual(ok.status_code, 200)
