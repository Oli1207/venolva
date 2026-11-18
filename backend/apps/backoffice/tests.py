"""Tests de l'administration : réglages, commissions, reversements, remboursements, droits d'accès."""
import itertools
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.testing import client_for, make_gym, make_member
from apps.backoffice.config import commission_pct
from apps.backoffice.models import AuditLog, CommissionOverride, PlatformSettings
from apps.gyms.models import ClassBooking, GymClass
from apps.market.models import Listing, Report
from apps.payments.models import Payment, Payout, PayoutAccount
from apps.payments.services import (
    PayoutError, balance_for, cancel_payout, create_payout, eligible_payments, mark_payout_paid,
)
from apps.payments.tests import KEYS, Network
from apps.pros.models import Booking, ProProfile
from apps.pros.tests import at, day_ahead, make_pro

_ref = itertools.count(1)


def make_staff(name="Admin", superuser=False):
    u = make_member(name)
    u.is_staff = True
    u.is_superuser = superuser
    u.save()
    return u


def jwt_client(user):
    """Client avec un vrai jeton : contrairement à force_authenticate, il vérifie que le compte est actif."""
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


def set_cfg(**values):
    obj = PlatformSettings.load()
    for k, v in values.items():
        setattr(obj, k, v)
    obj.save()
    return obj


def paid_payment(payee, net=9000, amount=10000, ended_days_ago=5, payer=None, purpose="booking", target=1, status="paid"):
    """Un paiement déjà encaissé, dont le service a eu lieu il y a quelques jours."""
    return Payment.objects.create(
        user=payer or make_member("Client"), purpose=purpose, target_id=target, amount=amount, fee=amount - net, net=net,
        provider="jeko", method="wave", reference=f"DJZ-t{next(_ref)}", status=status, paid_at=timezone.now(), payee=payee,
        service_ends_at=timezone.now() - timedelta(days=ended_days_ago),
    )


def give_account(user, method="wave", number="0700000777", holder="Serge K."):
    return PayoutAccount.objects.create(user=user, method=method, number="+225" + number.lstrip("0") if len(number) == 9 else "+225" + number, holder_name=holder)


# --- Accès ------------------------------------------------------------------------------------------------------------------------


class AccessTests(APITestCase):
    URLS = [
        "/api/admin/dashboard/", "/api/admin/settings/", "/api/admin/audit/", "/api/admin/commissions/", "/api/admin/payments/",
        "/api/admin/payees/", "/api/admin/payouts/", "/api/admin/payouts/export/", "/api/admin/pro-applications/", "/api/admin/gyms/",
        "/api/admin/reports/", "/api/admin/users/", "/api/admin/webhooks/",
    ]

    def test_anonymous_gets_401_and_members_get_403_everywhere(self):
        member = make_member("Simple")
        for url in self.URLS:
            self.assertEqual(APIClient().get(url).status_code, 401, url)
            self.assertEqual(client_for(member).get(url).status_code, 403, url)

    def test_staff_can_read_everything(self):
        staff = make_staff()
        for url in self.URLS:
            self.assertEqual(client_for(staff).get(url).status_code, 200, url)

    def test_a_pro_or_gym_manager_is_not_staff(self):
        pro, _ = make_pro()
        self.assertEqual(client_for(pro).get("/api/admin/settings/").status_code, 403)

    def test_inactive_staff_loses_access(self):
        staff = make_staff()
        c = jwt_client(staff)
        self.assertEqual(c.get("/api/admin/settings/").status_code, 200)
        staff.is_active = False
        staff.save()
        self.assertEqual(c.get("/api/admin/settings/").status_code, 401)  # le jeton déjà émis ne suffit plus

    def test_is_staff_is_exposed_to_the_app_but_cannot_be_self_assigned(self):
        member = make_member("Simple")
        res = client_for(member).patch("/api/auth/me/", {"is_staff": True}, format="json")
        self.assertFalse(res.json()["is_staff"])
        member.refresh_from_db()
        self.assertFalse(member.is_staff)


# --- Réglages ----------------------------------------------------------------------------------------------------------------------


class SettingsTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.c = client_for(self.staff)

    def patch(self, **values):
        return self.c.patch("/api/admin/settings/", {"values": values}, format="json")

    def test_defaults_match_the_previous_behaviour(self):
        v = self.c.get("/api/admin/settings/").json()["values"]
        self.assertEqual(
            (v["commission_booking_pct"], v["payout_hold_days"], v["free_cancel_hours"], v["booking_lead_hours"], v["max_active_listings"], v["max_listing_photos"], v["otp_ttl_seconds"]),
            (0, 2, 24, 1, 10, 4, 300),
        )

    def test_schema_describes_every_setting_for_the_form(self):
        body = self.c.get("/api/admin/settings/").json()
        keys = {s["key"] for s in body["schema"]}
        self.assertEqual(keys, set(body["values"]))
        self.assertTrue(all(s["group"] in {g["key"] for g in body["groups"]} and s["label"] for s in body["schema"]))

    def test_update_is_saved_audited_and_attributed(self):
        res = self.patch(commission_booking_pct=12, payout_hold_days=5)
        self.assertEqual(res.status_code, 200, res.content)
        s = PlatformSettings.load()
        self.assertEqual((s.commission_booking_pct, s.payout_hold_days, s.updated_by), (12, 5, self.staff))
        log = AuditLog.objects.get(action="settings.update")
        self.assertEqual(log.actor, self.staff)
        self.assertEqual(log.detail["changes"], {"commission_booking_pct": [0, 12], "payout_hold_days": [2, 5]})

    def test_unchanged_values_leave_no_trace(self):
        self.patch(commission_booking_pct=0)
        self.assertFalse(AuditLog.objects.exists())

    def test_invalid_values_are_refused_and_nothing_is_saved(self):
        for bad in (
            {"commission_booking_pct": 51}, {"commission_booking_pct": -1}, {"commission_booking_pct": "10"}, {"commission_booking_pct": 10.5},
            {"commission_booking_pct": True}, {"payment_mode": "bitcoin"}, {"inconnu": 1}, {"otp_ttl_seconds": 5}, {"free_cancel_hours": 999},
        ):
            res = self.patch(**bad)
            self.assertEqual(res.status_code, 400, bad)
            self.assertIn("errors", res.json())
        self.assertEqual(PlatformSettings.load().commission_booking_pct, 0)
        self.assertFalse(AuditLog.objects.exists())

    def test_one_bad_value_blocks_the_whole_update(self):
        self.assertEqual(self.patch(commission_booking_pct=15, commission_class_pct=99).status_code, 400)
        self.assertEqual(PlatformSettings.load().commission_booking_pct, 0)

    def test_minimum_price_must_stay_below_maximum(self):
        self.assertEqual(self.patch(price_min_fcfa=2000, price_max_fcfa=1500).status_code, 400)
        self.assertEqual(self.patch(price_min_fcfa=900_000).status_code, 200)  # max par défaut : 5 000 000
        self.assertEqual(self.patch(price_max_fcfa=800_000).status_code, 400)  # passerait sous le minimum

    def test_empty_body_is_refused(self):
        self.assertEqual(self.c.patch("/api/admin/settings/", {}, format="json").status_code, 400)
        self.assertEqual(self.c.patch("/api/admin/settings/", {"values": {}}, format="json").status_code, 400)

    def test_members_cannot_change_settings(self):
        res = client_for(make_member("Simple")).patch("/api/admin/settings/", {"values": {"commission_booking_pct": 50}}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(PlatformSettings.load().commission_booking_pct, 0)

    def test_audit_trail_is_readable_and_filterable(self):
        self.patch(commission_booking_pct=5)
        rows = self.c.get("/api/admin/audit/?action=settings").json()["results"]
        self.assertEqual([r["action"] for r in rows], ["settings.update"])
        self.assertEqual(rows[0]["actor"]["id"], self.staff.id)
        self.assertEqual(self.c.get("/api/admin/audit/?action=payout").json()["results"], [])


class SettingsTakeEffectTests(APITestCase):
    """Un réglage modifié change vraiment le comportement de l'app, sans redémarrage."""

    def test_booking_lead_time(self):
        pro, svc = make_pro()
        me = make_member("Olivier K.")
        soon = (timezone.now() + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
        with patch("apps.pros.serializers.slots.inside_availability", return_value=True):
            ok = client_for(me).post("/api/bookings/", {"service": svc.id, "starts_at": soon.isoformat()}, format="json")
            self.assertEqual(ok.status_code, 201, ok.content)
            set_cfg(booking_lead_hours=6)
            late = client_for(make_member("Autre")).post("/api/bookings/", {"service": svc.id, "starts_at": (soon + timedelta(hours=1)).isoformat()}, format="json")
        self.assertEqual(late.status_code, 400)
        self.assertIn("6 h", str(late.json()))

    def test_listing_limits(self):
        member = make_member("Vendeur")
        body = {"title": "Haltères", "price": 5000, "category": "weights"}
        set_cfg(max_active_listings=1)
        self.assertEqual(client_for(member).post("/api/listings/", body, format="json").status_code, 201)
        self.assertEqual(client_for(member).post("/api/listings/", body, format="json").status_code, 400)
        set_cfg(price_min_fcfa=1000, max_active_listings=5)
        self.assertEqual(client_for(member).post("/api/listings/", {**body, "price": 800}, format="json").status_code, 400)

    def test_service_price_limits(self):
        pro, _ = make_pro()
        set_cfg(price_max_fcfa=20000)
        res = client_for(pro).post("/api/my/services/", {"name": "Cher", "price": 30000, "modes": ["gym"], "duration_min": 60}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_otp_rules(self):
        set_cfg(otp_max_requests_per_hour=1)
        c = APIClient()
        self.assertEqual(c.post("/api/auth/otp/request/", {"email": "a444@exemple.test"}, format="json").status_code, 200)
        self.assertEqual(c.post("/api/auth/otp/request/", {"email": "a444@exemple.test"}, format="json").status_code, 429)

    def test_otp_code_lifetime(self):
        set_cfg(otp_ttl_seconds=60)
        c = APIClient()
        code = c.post("/api/auth/otp/request/", {"email": "a445@exemple.test"}, format="json").json()["dev_code"]
        from apps.accounts.models import OtpCode

        OtpCode.objects.update(created_at=timezone.now() - timedelta(seconds=90))
        self.assertEqual(c.post("/api/auth/otp/verify/", {"email": "a445@exemple.test", "code": code}, format="json").status_code, 400)


# --- Commissions ---------------------------------------------------------------------------------------------------------------------


class CommissionTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.c = client_for(self.staff)
        self.pro = make_member("Coach Serge")

    def test_rate_priority_is_specific_then_general_then_default(self):
        set_cfg(commission_booking_pct=10, commission_class_pct=8)
        self.assertEqual((commission_pct(self.pro, "booking"), commission_pct(self.pro, "class")), (10, 8))
        CommissionOverride.objects.create(user=self.pro, purpose="all", pct=5)
        self.assertEqual((commission_pct(self.pro, "booking"), commission_pct(self.pro, "class")), (5, 5))
        CommissionOverride.objects.create(user=self.pro, purpose="booking", pct=0)
        self.assertEqual((commission_pct(self.pro, "booking"), commission_pct(self.pro, "class")), (0, 5))
        self.assertEqual(commission_pct(make_member("Autre"), "booking"), 10)  # les autres gardent le taux par défaut
        self.assertEqual(commission_pct(None, "class"), 8)

    def test_set_replace_and_delete_an_override(self):
        res = self.c.post("/api/admin/commissions/", {"phone": self.pro.phone, "purpose": "booking", "pct": 4, "note": "Partenaire"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.c.post("/api/admin/commissions/", {"phone": self.pro.phone[-10:], "purpose": "booking", "pct": 6}, format="json")  # numéro sans +225
        self.assertEqual(CommissionOverride.objects.count(), 1)
        self.assertEqual(CommissionOverride.objects.get().pct, 6)
        rows = self.c.get("/api/admin/commissions/").json()
        self.assertEqual((rows[0]["user"]["id"], rows[0]["pct"]), (self.pro.id, 6))
        self.assertEqual(self.c.delete(f"/api/admin/commissions/{rows[0]['id']}/").status_code, 204)
        self.assertEqual(CommissionOverride.objects.count(), 0)
        self.assertEqual(list(AuditLog.objects.values_list("action", flat=True).order_by("id")), ["commission.set", "commission.set", "commission.delete"])

    def test_validation(self):
        def post(**b):
            return self.c.post("/api/admin/commissions/", {"phone": self.pro.phone, "purpose": "all", "pct": 5, **b}, format="json")
        self.assertEqual(post(pct=51).status_code, 400)
        self.assertEqual(post(pct="5").status_code, 400)
        self.assertEqual(post(purpose="loterie").status_code, 400)
        self.assertEqual(post(phone="0799999999").status_code, 400)
        self.assertEqual(post(phone="n'importe quoi").status_code, 400)

    def test_members_cannot_grant_themselves_a_rate(self):
        me = make_member("Malin")
        res = client_for(me).post("/api/admin/commissions/", {"phone": me.phone, "purpose": "all", "pct": 0}, format="json")
        self.assertEqual(res.status_code, 403)

    @override_settings(**KEYS)
    def test_the_rate_is_applied_and_frozen_on_each_payment(self):
        net = Network()
        with patch("requests.request", side_effect=net):
            set_cfg(commission_booking_pct=10)
            pro, svc = make_pro(price=20000)
            CommissionOverride.objects.create(user=pro, purpose="booking", pct=4)
            client = make_member("Olivier K.")
            b = Booking.objects.create(service=svc, pro=pro, client=client, status="confirmed", starts_at=at(day_ahead(), 9), ends_at=at(day_ahead(), 10), price_total=20000, price_client=20000)
            res = client_for(client).post("/api/payments/", {"purpose": "booking", "target": b.id, "method": "wave"}, format="json")
            self.assertEqual(res.status_code, 201, res.content)
            p = Payment.objects.get()
            self.assertEqual((p.commission_pct, p.fee, p.net), (4, 800, 19200))
            set_cfg(commission_booking_pct=30)
            CommissionOverride.objects.all().delete()
            p.refresh_from_db()
            self.assertEqual((p.commission_pct, p.fee, p.net), (4, 800, 19200))  # un changement ultérieur ne réécrit pas l'historique


# --- Soldes et reversements ---------------------------------------------------------------------------------------------------------


class BalanceTests(APITestCase):
    def setUp(self):
        self.pro = make_member("Coach Serge")

    def test_buckets_follow_the_hold_period(self):
        paid_payment(self.pro, net=9000, ended_days_ago=5)   # disponible
        paid_payment(self.pro, net=4500, ended_days_ago=1)   # service trop récent : en attente
        paid_payment(self.pro, net=3000, ended_days_ago=5, status="refund_due")  # remboursement dû : jamais payable
        paid_payment(self.pro, net=700, ended_days_ago=5, status="pending")
        b = balance_for(self.pro)
        self.assertEqual((b["available"], b["waiting"], b["refund_pending"]), (9000, 4500, 3000))

    def test_changing_the_hold_period_moves_money_between_buckets(self):
        paid_payment(self.pro, net=4500, ended_days_ago=1)
        self.assertEqual(balance_for(self.pro)["available"], 0)
        set_cfg(payout_hold_days=0)
        self.assertEqual(balance_for(self.pro)["available"], 4500)

    def test_a_future_service_is_never_available(self):
        paid_payment(self.pro, net=8000, ended_days_ago=-3)
        self.assertEqual(balance_for(self.pro)["available"], 0)

    def test_other_people_money_is_not_mixed_in(self):
        paid_payment(make_member("Autre pro"), net=9000)
        self.assertEqual(balance_for(self.pro), {"available": 0, "waiting": 0, "in_payout": 0, "paid_out": 0, "refund_pending": 0})


class PayoutTests(APITestCase):
    def setUp(self):
        self.admin = make_staff()
        self.pro = make_member("Coach Serge")

    def test_needs_an_account_a_balance_and_the_minimum(self):
        with self.assertRaisesRegex(PayoutError, "Rien à reverser"):
            create_payout(self.pro, self.admin)
        paid_payment(self.pro, net=9000)
        with self.assertRaisesRegex(PayoutError, "où recevoir"):
            create_payout(self.pro, self.admin)
        give_account(self.pro)
        set_cfg(min_payout_fcfa=20000)
        with self.assertRaisesRegex(PayoutError, "minimum"):
            create_payout(self.pro, self.admin)

    def test_payout_collects_only_available_payments_and_locks_them(self):
        a = paid_payment(self.pro, net=9000)
        b = paid_payment(self.pro, net=6000)
        waiting = paid_payment(self.pro, net=4000, ended_days_ago=0)
        give_account(self.pro)
        payout = create_payout(self.pro, self.admin)
        self.assertEqual((payout.amount, payout.status, payout.created_by), (15000, "pending", self.admin))
        self.assertEqual(set(payout.payments.values_list("pk", flat=True)), {a.pk, b.pk})
        waiting.refresh_from_db()
        self.assertIsNone(waiting.payout)
        # ces paiements ne comptent plus comme disponibles : pas de double versement
        self.assertEqual(eligible_payments(self.pro).count(), 0)
        with self.assertRaises(PayoutError):
            create_payout(self.pro, self.admin)
        bal = balance_for(self.pro)
        self.assertEqual((bal["available"], bal["in_payout"], bal["paid_out"]), (0, 15000, 0))

    def test_payout_keeps_a_copy_of_the_account(self):
        paid_payment(self.pro)
        acct = give_account(self.pro, method="wave", number="0700000777", holder="Serge K.")
        payout = create_payout(self.pro, self.admin)
        acct.method, acct.number = "orange", "+2250799999999"
        acct.save()
        payout.refresh_from_db()
        self.assertEqual((payout.method, payout.number, payout.holder_name), ("wave", "+2250700000777", "Serge K."))

    def test_marking_paid_needs_a_reference_and_is_final(self):
        paid_payment(self.pro)
        give_account(self.pro)
        payout = create_payout(self.pro, self.admin)
        with self.assertRaisesRegex(PayoutError, "référence"):
            mark_payout_paid(payout, "  ")
        mark_payout_paid(payout, "WAVE-TX-42")
        payout.refresh_from_db()
        self.assertEqual((payout.status, payout.reference), ("paid", "WAVE-TX-42"))
        self.assertIsNotNone(payout.paid_at)
        self.assertEqual(balance_for(self.pro)["paid_out"], 9000)
        with self.assertRaises(PayoutError):
            mark_payout_paid(payout, "AUTRE")
        with self.assertRaises(PayoutError):
            cancel_payout(payout)

    def test_cancelling_releases_the_payments(self):
        p = paid_payment(self.pro)
        give_account(self.pro)
        payout = create_payout(self.pro, self.admin)
        cancel_payout(payout)
        p.refresh_from_db()
        self.assertIsNone(p.payout)
        self.assertEqual(balance_for(self.pro)["available"], 9000)
        self.assertEqual(create_payout(self.pro, self.admin).amount, 9000)  # on peut le refaire

    # --- via l'API ---
    def test_admin_api_flow(self):
        paid_payment(self.pro, net=9000)
        c = client_for(self.admin)
        payees = c.get("/api/admin/payees/").json()
        self.assertEqual((payees[0]["user"]["id"], payees[0]["available"], payees[0]["account"]), (self.pro.id, 9000, None))
        self.assertEqual(c.post("/api/admin/payouts/", {"payee": self.pro.id}, format="json").status_code, 400)  # pas de compte
        give_account(self.pro)
        res = c.post("/api/admin/payouts/", {"payee": self.pro.id}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        pid = res.json()["id"]
        self.assertEqual(len(res.json()["payments"]), 1)
        self.assertEqual(c.post(f"/api/admin/payouts/{pid}/paid/", {}, format="json").status_code, 400)
        done = c.post(f"/api/admin/payouts/{pid}/paid/", {"reference": "WAVE-1"}, format="json")
        self.assertEqual((done.status_code, done.json()["status"]), (200, "paid"))
        self.assertEqual(c.post(f"/api/admin/payouts/{pid}/cancel/").status_code, 400)
        self.assertEqual(c.post(f"/api/admin/payouts/{pid}/zzz/").status_code, 404)
        self.assertEqual([r["action"] for r in c.get("/api/admin/audit/?action=payout").json()["results"]], ["payout.paid", "payout.create"])
        self.assertEqual(c.get("/api/admin/payees/?available=1").json(), [])

    def test_only_staff_can_create_or_settle_payouts(self):
        paid_payment(self.pro)
        give_account(self.pro)
        me = client_for(self.pro)
        self.assertEqual(me.post("/api/admin/payouts/", {"payee": self.pro.id}, format="json").status_code, 403)
        payout = create_payout(self.pro, self.admin)
        self.assertEqual(me.post(f"/api/admin/payouts/{payout.id}/paid/", {"reference": "X"}, format="json").status_code, 403)
        payout.refresh_from_db()
        self.assertEqual(payout.status, "pending")

    def test_csv_export_for_bulk_transfers_neutralizes_formulas(self):
        evil = make_member("=HYPERLINK(\"http://x\")")
        paid_payment(evil, net=9000)
        give_account(evil, holder="+cmd|calc")
        create_payout(evil, self.admin)
        res = client_for(self.admin).get("/api/admin/payouts/export/?status=pending")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res["Content-Type"].startswith("text/csv"))
        text = res.content.decode("utf-8-sig")
        self.assertIn("Montant FCFA", text.splitlines()[0])
        self.assertIn("9000", text)
        self.assertNotIn(";=HYPERLINK", text)
        self.assertIn("'=HYPERLINK", text)
        self.assertIn("'+cmd", text)
        self.assertEqual(client_for(make_member("Simple")).get("/api/admin/payouts/export/").status_code, 403)

    def test_payee_sees_own_balance_and_manages_the_payout_account(self):
        paid_payment(self.pro, net=9000)
        paid_payment(self.pro, net=4000, ended_days_ago=0)
        c = client_for(self.pro)
        body = c.get("/api/my/earnings/").json()
        self.assertEqual((body["balance"]["available"], body["balance"]["waiting"], body["account"], body["hold_days"], body["min_payout"]), (9000, 4000, None, 2, 5000))
        self.assertEqual(len(body["payments"]), 2)
        self.assertIsNotNone(body["payments"][0]["available_at"])
        bad = c.put("/api/my/payout-account/", {"method": "paypal", "number": "0700000777", "holder_name": "Serge"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(c.put("/api/my/payout-account/", {"method": "wave", "number": "12", "holder_name": "Serge"}, format="json").status_code, 400)
        self.assertEqual(c.put("/api/my/payout-account/", {"method": "wave", "number": "0700000777", "holder_name": "S"}, format="json").status_code, 400)
        ok = c.put("/api/my/payout-account/", {"method": "wave", "number": "07 00 00 07 77", "holder_name": "Serge K."}, format="json")
        self.assertEqual((ok.status_code, ok.json()["number"]), (200, "+2250700000777"))
        self.assertEqual(c.get("/api/my/payout-account/").json()["holder_name"], "Serge K.")
        self.assertEqual(c.get("/api/my/earnings/").json()["account"]["method"], "wave")

    def test_earnings_never_leak_to_other_members(self):
        paid_payment(self.pro, net=9000)
        other = client_for(make_member("Autre")).get("/api/my/earnings/").json()
        self.assertEqual((other["payments"], other["balance"]["available"]), ([], 0))


# --- Remboursements -------------------------------------------------------------------------------------------------------------------


@override_settings(**KEYS)
class RefundPolicyTests(APITestCase):
    def setUp(self):
        self.pro, self.svc = make_pro(price=10000)
        self.client_user = make_member("Olivier K.")

    def booking(self, hours_ahead=72, paid=True):
        start = timezone.now() + timedelta(hours=hours_ahead)
        b = Booking.objects.create(service=self.svc, pro=self.pro, client=self.client_user, status="confirmed", starts_at=start, ends_at=start + timedelta(hours=1), price_total=10000, price_client=10000)
        p = paid_payment(self.pro, payer=self.client_user, target=b.id, status="paid" if paid else "pending")
        return b, p

    def cancel(self, user, b):
        return client_for(user).post(f"/api/bookings/{b.id}/cancel/")

    def test_early_cancellation_by_the_client_refunds(self):
        b, p = self.booking(hours_ahead=72)
        self.assertEqual(self.cancel(self.client_user, b).status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "refund_due")
        self.assertEqual(balance_for(self.pro)["available"], 0)

    def test_late_cancellation_by_the_client_keeps_the_money_with_the_pro(self):
        b, p = self.booking(hours_ahead=5)
        self.cancel(self.client_user, b)
        p.refresh_from_db()
        self.assertEqual(p.status, "paid")

    def test_the_free_cancellation_window_is_a_setting(self):
        set_cfg(free_cancel_hours=2)
        b, p = self.booking(hours_ahead=5)
        self.cancel(self.client_user, b)
        p.refresh_from_db()
        self.assertEqual(p.status, "refund_due")

    def test_a_cancellation_by_the_pro_always_refunds(self):
        b, p = self.booking(hours_ahead=3)
        self.cancel(self.pro, b)
        p.refresh_from_db()
        self.assertEqual(p.status, "refund_due")

    def test_unfinished_payment_attempts_are_closed(self):
        b, p = self.booking(paid=False)
        self.cancel(self.client_user, b)
        p.refresh_from_db()
        self.assertEqual(p.status, "expired")

    def test_money_already_in_a_payout_is_not_touched(self):
        b, p = self.booking(hours_ahead=72)
        payout = Payout.objects.create(payee=self.pro, amount=9000, method="wave", number="+2250700000777", holder_name="S")
        Payment.objects.filter(pk=p.pk).update(payout=payout)
        self.cancel(self.client_user, b)
        p.refresh_from_db()
        self.assertEqual(p.status, "paid")

    def test_class_seat_refund_rules(self):
        gym = make_gym()
        owner = make_member("Gérant")
        gym.owner = owner
        gym.save()
        cls = GymClass.objects.create(gym=gym, name="Zumba", starts_at=timezone.now() + timedelta(days=3), capacity=5, price=2000)
        seat = ClassBooking.objects.create(gym_class=cls, user=self.client_user, paid=True)
        p = paid_payment(owner, payer=self.client_user, purpose="class", target=seat.id, net=2000, amount=2000)
        self.assertEqual(client_for(self.client_user).post(f"/api/gym-classes/{cls.id}/cancel/").status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "refund_due")
        self.assertFalse(ClassBooking.objects.filter(pk=seat.pk).exists())

    def test_a_class_cancelled_by_the_gym_refunds_everyone(self):
        gym = make_gym()
        owner = make_member("Gérant")
        owner.pro_type, owner.pro_verified = "gym", True
        owner.save()
        gym.owner = owner
        gym.save()
        cls = GymClass.objects.create(gym=gym, name="Zumba", starts_at=timezone.now() + timedelta(hours=3), capacity=5, price=2000)
        payments = []
        for n in ("A", "B"):
            seat = ClassBooking.objects.create(gym_class=cls, user=make_member(n), paid=True)
            payments.append(paid_payment(owner, payer=seat.user, purpose="class", target=seat.id, net=2000, amount=2000))
        self.assertEqual(client_for(owner).delete(f"/api/my/gym/classes/{cls.id}/").status_code, 204)
        for p in payments:
            p.refresh_from_db()
            self.assertEqual(p.status, "refund_due")

    # --- action de l'administrateur ---
    def test_admin_marks_a_refund_as_done(self):
        b, p = self.booking(hours_ahead=72)
        self.cancel(self.client_user, b)
        admin = client_for(make_staff())
        res = admin.post(f"/api/admin/payments/{p.id}/refund/", {"reference": "PSK-REFUND-9"}, format="json")
        self.assertEqual((res.status_code, res.json()["status"]), (200, "refunded"))
        p.refresh_from_db()
        self.assertEqual((p.refund_reference, p.refunded_at is not None), ("PSK-REFUND-9", True))
        self.assertEqual(admin.post(f"/api/admin/payments/{p.id}/refund/", {}, format="json").status_code, 400)  # déjà remboursé
        self.assertTrue(AuditLog.objects.filter(action="payment.refund").exists())

    def test_a_normal_paid_payment_cannot_be_marked_refunded(self):
        p = paid_payment(self.pro)
        self.assertEqual(client_for(make_staff()).post(f"/api/admin/payments/{p.id}/refund/", {}, format="json").status_code, 400)
        p.refresh_from_db()
        self.assertEqual(p.status, "paid")

    def test_accepting_a_payment_under_review_applies_it(self):
        b, _ = self.booking(hours_ahead=72)
        p = paid_payment(self.pro, payer=self.client_user, target=b.id, status="review")
        res = client_for(make_staff()).post(f"/api/admin/payments/{p.id}/accept/")
        self.assertEqual((res.status_code, res.json()["status"]), (200, "paid"))
        b.refresh_from_db()
        self.assertEqual(b.payment_status, "paid")
        self.assertEqual(client_for(make_staff()).post(f"/api/admin/payments/{p.id}/accept/").status_code, 400)

    def test_members_cannot_trigger_admin_payment_actions(self):
        p = paid_payment(self.pro, status="refund_due")
        self.assertEqual(client_for(self.client_user).post(f"/api/admin/payments/{p.id}/refund/", {}, format="json").status_code, 403)


# --- Paiements, tableau de bord ----------------------------------------------------------------------------------------------------------


class PaymentsAdminTests(APITestCase):
    def setUp(self):
        self.admin = make_staff()
        self.pro = make_member("Coach Serge")

    def test_list_filters_and_search(self):
        paid_payment(self.pro, status="paid")
        paid_payment(self.pro, status="review")
        c = client_for(self.admin)
        self.assertEqual(c.get("/api/admin/payments/").json()["count"], 2)
        self.assertEqual(c.get("/api/admin/payments/?status=review").json()["count"], 1)
        self.assertEqual(c.get("/api/admin/payments/?provider=paystack").json()["count"], 0)
        self.assertEqual(c.get("/api/admin/payments/?q=Client").json()["count"], 2)
        row = c.get("/api/admin/payments/?status=paid").json()["results"][0]
        self.assertEqual((row["payee"]["id"], row["amount"], row["net"]), (self.pro.id, 10000, 9000))

    def test_dashboard_numbers(self):
        paid_payment(self.pro, net=9000, amount=10000)
        paid_payment(self.pro, net=4500, amount=5000, ended_days_ago=0)
        paid_payment(self.pro, status="refund_due")
        ProProfile.objects.create(user=make_member("Candidat"), credential="X123", status="pending")
        d = client_for(self.admin).get("/api/admin/dashboard/").json()
        self.assertEqual(d["payments_30d"], {"count": 2, "gross": 15000, "fees": 1500})
        self.assertEqual((d["payouts"]["available"], d["pros_pending"], d["refunds"]["count"]), (9000, 1, 1))
        self.assertFalse(d["commission_set"])
        set_cfg(commission_booking_pct=10)
        self.assertTrue(client_for(self.admin).get("/api/admin/dashboard/").json()["commission_set"])

    def test_webhook_journal_is_visible(self):
        from apps.payments.models import WebhookEvent

        WebhookEvent.objects.create(provider="jeko", event="TRANSACTION_COMPLETED", reference="DJZ-1", outcome="processed")
        rows = client_for(self.admin).get("/api/admin/webhooks/").json()["results"]
        self.assertEqual((rows[0]["provider"], rows[0]["outcome"]), ("jeko", "processed"))


# --- Dossiers pro, salles, modération, utilisateurs -----------------------------------------------------------------------------------------


class ProApplicationAdminTests(APITestCase):
    def setUp(self):
        self.admin = client_for(make_staff())
        self.user = make_member("Fatou D.")
        self.user.pro_type = "nutrition"
        self.user.save()
        self.app = ProProfile.objects.create(user=self.user, credential="N° ordre 4521", speciality="Nutrition", status="pending")

    def test_pending_list_then_approve(self):
        rows = self.admin.get("/api/admin/pro-applications/").json()["results"]
        self.assertEqual((rows[0]["credential"], rows[0]["pro_type"]), ("N° ordre 4521", "nutrition"))
        self.assertEqual(self.admin.post(f"/api/admin/pro-applications/{self.app.id}/approve/").json()["status"], "approved")
        self.user.refresh_from_db()
        self.assertTrue(self.user.pro_verified)
        self.assertEqual(self.admin.get("/api/admin/pro-applications/").json()["count"], 0)
        self.assertEqual(self.admin.get("/api/admin/pro-applications/?status=all").json()["count"], 1)
        self.assertTrue(AuditLog.objects.filter(action="pro.approve").exists())

    def test_reject_with_a_note_shown_to_the_applicant(self):
        self.admin.post(f"/api/admin/pro-applications/{self.app.id}/reject/", {"note": "Diplôme illisible"}, format="json")
        state = client_for(self.user).get("/api/pro/me/").json()
        self.assertEqual((state["status"], state["review_note"]), ("rejected", "Diplôme illisible"))

    def test_unknown_action_and_members(self):
        self.assertEqual(self.admin.post(f"/api/admin/pro-applications/{self.app.id}/explode/").status_code, 404)
        self.assertEqual(client_for(self.user).post(f"/api/admin/pro-applications/{self.app.id}/approve/").status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.pro_verified)  # on ne se valide pas soi-même


class GymAndModerationAdminTests(APITestCase):
    def setUp(self):
        self.admin = client_for(make_staff())

    def test_assign_and_detach_a_gym_owner(self):
        gym = make_gym("Salle X")
        boss = make_member("Futur gérant")
        res = self.admin.patch(f"/api/admin/gyms/{gym.id}/", {"owner_phone": boss.phone, "verified": True}, format="json")
        self.assertEqual((res.status_code, res.json()["owner"]["id"], res.json()["verified"]), (200, boss.id, True))
        self.assertEqual(client_for(boss).get("/api/my/gym/").status_code, 200)  # l'accès gérant s'ouvre
        self.admin.patch(f"/api/admin/gyms/{gym.id}/", {"owner_phone": ""}, format="json")
        gym.refresh_from_db()
        self.assertIsNone(gym.owner)

    def test_gym_validation_errors(self):
        gym = make_gym()
        self.assertEqual(self.admin.patch(f"/api/admin/gyms/{gym.id}/", {"owner_phone": "0799999999"}, format="json").status_code, 400)
        self.assertEqual(self.admin.patch(f"/api/admin/gyms/{gym.id}/", {"verified": "oui"}, format="json").status_code, 400)
        self.assertEqual(client_for(make_member("Simple")).patch(f"/api/admin/gyms/{gym.id}/", {"verified": True}, format="json").status_code, 403)

    def test_hide_a_reported_listing(self):
        seller, reporter = make_member("Vendeur"), make_member("Acheteur")
        listing = Listing.objects.create(seller=seller, title="Arnaque", price=1000, category="weights")
        report = Report.objects.create(listing=listing, reporter=reporter, reason="scam")
        rows = self.admin.get("/api/admin/reports/").json()["results"]
        self.assertEqual((rows[0]["listing"]["title"], rows[0]["reports_on_listing"]), ("Arnaque", 1))
        self.assertEqual(self.admin.post(f"/api/admin/reports/{report.id}/hide/").status_code, 200)
        listing.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual((listing.status, report.handled), ("hidden", True))
        self.assertEqual(self.admin.get("/api/admin/reports/").json()["count"], 0)

    def test_dismiss_a_report_keeps_the_listing(self):
        listing = Listing.objects.create(seller=make_member("Vendeur"), title="OK", price=1000, category="weights")
        report = Report.objects.create(listing=listing, reporter=make_member("A"), reason="other")
        self.admin.post(f"/api/admin/reports/{report.id}/dismiss/")
        listing.refresh_from_db()
        self.assertEqual(listing.status, "active")


class UserAdminTests(APITestCase):
    def setUp(self):
        self.admin = make_staff("Admin")
        self.root = make_staff("Root", superuser=True)
        self.member = make_member("Awa K.")

    def test_search_and_pagination_shape(self):
        res = client_for(self.admin).get("/api/admin/users/?q=Awa").json()
        self.assertEqual((res["count"], res["results"][0]["id"]), (1, self.member.id))
        self.assertIn("phone", res["results"][0])

    def test_suspended_accounts_are_locked_out_immediately(self):
        member_session = jwt_client(self.member)
        self.assertEqual(member_session.get("/api/auth/me/").status_code, 200)
        res = client_for(self.admin).patch(f"/api/admin/users/{self.member.id}/", {"is_active": False}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(member_session.get("/api/auth/me/").status_code, 401)
        client_for(self.admin).patch(f"/api/admin/users/{self.member.id}/", {"is_active": True}, format="json")
        self.assertEqual(member_session.get("/api/auth/me/").status_code, 200)

    def test_only_a_superuser_grants_admin_access(self):
        self.assertEqual(client_for(self.admin).patch(f"/api/admin/users/{self.member.id}/", {"is_staff": True}, format="json").status_code, 403)
        self.assertEqual(client_for(self.root).patch(f"/api/admin/users/{self.member.id}/", {"is_staff": True}, format="json").status_code, 200)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_staff)
        self.assertEqual(client_for(self.member).get("/api/admin/dashboard/").status_code, 200)

    def test_nobody_edits_themselves_or_a_superuser(self):
        self.assertEqual(client_for(self.admin).patch(f"/api/admin/users/{self.admin.id}/", {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(client_for(self.admin).patch(f"/api/admin/users/{self.root.id}/", {"is_active": False}, format="json").status_code, 403)
        self.root.refresh_from_db()
        self.assertTrue(self.root.is_active)

    def test_validation_and_audit(self):
        self.assertEqual(client_for(self.admin).patch(f"/api/admin/users/{self.member.id}/", {"is_active": "non"}, format="json").status_code, 400)
        client_for(self.admin).patch(f"/api/admin/users/{self.member.id}/", {"is_active": False}, format="json")
        log = AuditLog.objects.get(action="user.update")
        self.assertEqual((log.actor, log.target, log.detail["changes"]["is_active"]), (self.admin, f"user:{self.member.id}", [True, False]))
