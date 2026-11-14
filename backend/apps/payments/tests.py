"""Tests du paiement en ligne. Aucun appel réseau : les prestataires sont simulés, et les clés sont celles du test."""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

import requests
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.backoffice.models import PlatformSettings
from apps.gyms.models import ClassBooking, GymClass
from apps.pros.models import Booking
from apps.pros.tests import at, day_ahead, make_pro

from .models import Payment, WebhookEvent
from .services import available_methods

KEYS = dict(
    PAYMENT_MODE="auto",
    PAYSTACK_SECRET_KEY="sk_test_fake", PAYSTACK_WEBHOOK_SECRET="sk_test_fake", PAYSTACK_CURRENCY="XOF",
    JEKO_API_KEY="jk_fake", JEKO_API_KEY_ID="jid_fake", JEKO_STORE_ID="store-1", JEKO_WEBHOOK_SECRET="whsec_fake", JEKO_CURRENCY="XOF",
    FRONTEND_URL="http://front.test",
)
PAYSTACK_ONLY = {**KEYS, "JEKO_API_KEY": "", "JEKO_API_KEY_ID": "", "JEKO_STORE_ID": ""}
NO_KEYS = {**PAYSTACK_ONLY, "PAYSTACK_SECRET_KEY": "", "PAYSTACK_WEBHOOK_SECRET": ""}


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body if body is not None else {}

    def json(self):
        return self._body


class Network:
    """Simule Paystack et Jeko. Garde la trace des appels pour vérifier ce qui est envoyé."""

    def __init__(self):
        self.calls = []
        self.jeko_down = False
        self.paystack_down = False
        self.paystack_verify = {"status": "abandoned"}
        self.jeko_status = {"status": "pending"}

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if "jeko" in url:
            if self.jeko_down:
                return FakeResponse(500, {"error": "boom"})
            if method == "POST":
                return FakeResponse(200, {"id": "pr_123", "redirectUrl": "https://pay.jeko.test/checkout/pr_123"})
            return FakeResponse(200, self.jeko_status)
        if self.paystack_down:
            raise requests.ConnectionError("réseau coupé")
        if method == "POST":
            return FakeResponse(200, {"status": True, "data": {"authorization_url": "https://checkout.paystack.test/abc", "access_code": "ac", "reference": kwargs["json"]["reference"]}})
        return FakeResponse(200, {"status": True, "data": self.paystack_verify})

    def sent_to(self, host):
        return [c for c in self.calls if host in c[1]]


def paystack_sig(raw: bytes) -> str:
    return hmac.new(b"sk_test_fake", raw, hashlib.sha512).hexdigest()


def jeko_sig(raw: bytes) -> str:
    return hmac.new(b"whsec_fake", raw, hashlib.sha256).hexdigest()


def make_confirmed_booking(price=10000, kind="single", partner=None):
    pro, service = make_pro(price=price, kind=kind)
    client = make_member("Olivier K.")
    booking = Booking.objects.create(
        service=service, pro=pro, client=client, partner=partner, status="confirmed",
        starts_at=at(day_ahead(), 9), ends_at=at(day_ahead(), 10),
        price_total=price, price_client=-(-price // 2) if partner else price,
    )
    return booking, pro, client


@override_settings(**KEYS)
class MethodsTests(APITestCase):
    def test_both_providers(self):
        codes = [m["code"] for m in available_methods()]
        self.assertEqual(codes, ["wave", "orange", "mtn", "moov", "card"])

    @override_settings(**PAYSTACK_ONLY)
    def test_paystack_only_offers_generic_mobile_money(self):
        self.assertEqual([m["code"] for m in available_methods()], ["mobile", "card"])

    @override_settings(**NO_KEYS)
    def test_nothing_without_keys(self):
        self.assertEqual(available_methods(), [])

    def test_jeko_mode_has_no_card(self):
        PlatformSettings.objects.update_or_create(pk=1, defaults={"payment_mode": "jeko"})
        self.assertEqual([m["code"] for m in available_methods()], ["wave", "orange", "mtn", "moov"])

    def test_paystack_mode_ignores_jeko(self):
        PlatformSettings.objects.update_or_create(pk=1, defaults={"payment_mode": "paystack"})
        self.assertEqual([m["code"] for m in available_methods()], ["mobile", "card"])

    def test_incomplete_jeko_config_falls_back_to_paystack(self):
        # C'est le cas réel tant que JEKO_API_KEY_ID n'est pas renseignée.
        with override_settings(JEKO_API_KEY_ID=""):
            self.assertEqual([m["code"] for m in available_methods()], ["mobile", "card"])

    def test_endpoint_requires_login_and_lists_methods(self):
        self.assertEqual(APIClient().get("/api/payments/methods/").status_code, 401)
        res = client_for(make_member("A")).get("/api/payments/methods/")
        self.assertEqual(len(res.json()), 5)


@override_settings(**KEYS)
class CreatePaymentTests(APITestCase):
    def setUp(self):
        self.net = Network()
        patcher = patch("requests.request", side_effect=self.net)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.booking, self.pro, self.client_user = make_confirmed_booking()

    def pay(self, user=None, **body):
        data = {"purpose": "booking", "target": self.booking.id, "method": "wave"}
        data.update(body)
        return client_for(user or self.client_user).post("/api/payments/", data, format="json")

    def test_mobile_money_goes_through_jeko_with_the_exact_amount(self):
        res = self.pay()
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual((body["provider"], body["amount"]), ("jeko", 10000))
        self.assertEqual(body["checkout_url"], "https://pay.jeko.test/checkout/pr_123")
        sent = self.net.sent_to("jeko")[0][2]
        self.assertEqual(sent["json"]["amountCents"], 1_000_000)
        self.assertEqual(sent["json"]["storeId"], "store-1")
        self.assertEqual(sent["json"]["paymentDetails"]["data"]["paymentMethod"], "wave")
        self.assertTrue(sent["json"]["paymentDetails"]["data"]["successUrl"].startswith("http://front.test/paiement/retour?ref=DJZ-b"))
        headers = self.net.sent_to("jeko")[0][2]["headers"]
        self.assertEqual((headers["X-API-KEY"], headers["X-API-KEY-ID"]), ("jk_fake", "jid_fake"))
        payment = Payment.objects.get()
        self.assertEqual((payment.status, payment.user, payment.net, payment.fee), ("pending", self.client_user, 10000, 0))

    def test_card_goes_through_paystack_without_exposing_the_member_phone(self):
        res = self.pay(method="card")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["provider"], "paystack")
        sent = self.net.sent_to("paystack")[0][2]
        self.assertEqual(sent["json"]["amount"], 1_000_000)
        self.assertEqual(sent["json"]["currency"], "XOF")
        self.assertEqual(sent["json"]["email"], f"u{self.client_user.id}@pay.djinzin.app")
        self.assertNotIn(self.client_user.phone, json.dumps(sent["json"]))
        self.assertEqual(sent["headers"]["Authorization"], "Bearer sk_test_fake")

    def test_jeko_failure_falls_back_to_paystack(self):
        self.net.jeko_down = True
        res = self.pay()
        self.assertEqual((res.status_code, res.json()["provider"]), (201, "paystack"))

    def test_when_every_provider_fails_nothing_is_left_behind(self):
        self.net.jeko_down = self.net.paystack_down = True
        res = self.pay()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertNotIn("boom", json.dumps(res.json()))  # le détail du prestataire n'est jamais renvoyé

    @override_settings(**NO_KEYS)
    def test_without_keys_online_payment_is_refused(self):
        self.assertEqual(self.pay().status_code, 400)

    def test_unknown_method_and_purpose(self):
        self.assertEqual(self.pay(method="bitcoin").status_code, 400)
        self.assertEqual(self.pay(purpose="loterie").status_code, 400)
        self.assertEqual(self.pay(target="abc").status_code, 400)

    def test_only_a_confirmed_booking_can_be_paid_online(self):
        self.booking.status = "pending"
        self.booking.save()
        res = self.pay()
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirmé", res.json()["detail"])
        self.assertEqual(self.net.calls, [])  # le prestataire n'est même pas appelé

    def test_strangers_and_the_pro_cannot_pay_someone_elses_booking(self):
        self.assertEqual(self.pay(user=make_member("Intrus")).status_code, 400)
        self.assertEqual(self.pay(user=self.pro).status_code, 400)

    def test_cannot_pay_an_already_paid_booking(self):
        self.booking.payment_status = "paid"
        self.booking.save()
        self.assertEqual(self.pay().status_code, 400)

    def test_a_new_attempt_replaces_the_previous_pending_one(self):
        first = self.pay().json()["reference"]
        second = self.pay(method="orange").json()["reference"]
        self.assertNotEqual(first, second)
        self.assertEqual(Payment.objects.get(reference=first).status, "expired")
        self.assertEqual(Payment.objects.get(reference=second).status, "pending")

    def test_duo_each_person_pays_their_own_share(self):
        awa = make_member("Awa K.")
        booking, _, client = make_confirmed_booking(price=14001, kind="duo", partner=awa)
        c = client_for(client).post("/api/payments/", {"purpose": "booking", "target": booking.id, "method": "wave"}, format="json")
        a = client_for(awa).post("/api/payments/", {"purpose": "booking", "target": booking.id, "method": "wave"}, format="json")
        self.assertEqual((c.json()["amount"], a.json()["amount"]), (7001, 7000))

    def test_class_payment_needs_an_unpaid_priced_seat(self):
        gym = make_gym()
        cls = GymClass.objects.create(gym=gym, name="Zumba", starts_at=timezone.now() + timedelta(days=2), capacity=5, price=2000)
        free = GymClass.objects.create(gym=gym, name="Inclus", starts_at=timezone.now() + timedelta(days=2), capacity=5, price=0)
        me = make_member("Olivier K.")
        seat = ClassBooking.objects.create(gym_class=cls, user=me)
        free_seat = ClassBooking.objects.create(gym_class=free, user=me)
        ok = client_for(me).post("/api/payments/", {"purpose": "class", "target": seat.id, "method": "wave"}, format="json")
        self.assertEqual((ok.status_code, ok.json()["amount"]), (201, 2000))
        nope = client_for(me).post("/api/payments/", {"purpose": "class", "target": free_seat.id, "method": "wave"}, format="json")
        self.assertEqual(nope.status_code, 400)
        other = client_for(make_member("Autre")).post("/api/payments/", {"purpose": "class", "target": seat.id, "method": "wave"}, format="json")
        self.assertEqual(other.status_code, 400)

    def test_commission_is_recorded_for_future_payouts(self):
        PlatformSettings.objects.update_or_create(pk=1, defaults={"commission_booking_pct": 10})
        self.pay()
        payment = Payment.objects.get()
        self.assertEqual((payment.fee, payment.net, payment.commission_pct, payment.payee), (1000, 9000, 10, self.pro))
        self.assertEqual(payment.service_ends_at, self.booking.ends_at)


@override_settings(**KEYS)
class WebhookTests(APITestCase):
    def setUp(self):
        self.net = Network()
        patcher = patch("requests.request", side_effect=self.net)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.booking, self.pro, self.client_user = make_confirmed_booking()
        self.ref_jeko = client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": "wave"}, format="json").json()["reference"]

    # --- aides ---
    def paystack_hook(self, reference, amount=1_000_000, currency="XOF", event="charge.success", sig=None):
        raw = json.dumps({"event": event, "data": {"reference": reference, "amount": amount, "currency": currency, "paid_at": "2026-11-16T09:00:00.000Z"}}).encode()
        return self.client.post("/api/payments/webhooks/paystack/", data=raw, content_type="application/json",
                                HTTP_X_PAYSTACK_SIGNATURE=sig if sig is not None else paystack_sig(raw))

    def jeko_hook(self, reference, amount=1_000_000, currency="XOF", event="TRANSACTION_COMPLETED", status="success", sig=None):
        raw = json.dumps({"status": status, "transactionDetails": {"reference": reference}, "amount": {"amount": amount, "currency": currency}, "executedAt": "2026-11-16 09:00:00"}).encode()
        return self.client.post("/api/payments/webhooks/jeko/", data=raw, content_type="application/json",
                                HTTP_JEKO_SIGNATURE=sig if sig is not None else jeko_sig(raw), HTTP_JEKO_EVENT=event)

    def status_of(self, reference):
        return Payment.objects.get(reference=reference).status

    # --- Jeko ---
    def test_jeko_success_marks_payment_and_booking_paid(self):
        self.assertEqual(self.jeko_hook(self.ref_jeko).status_code, 200)
        self.assertEqual(self.status_of(self.ref_jeko), "paid")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, "paid")
        self.assertEqual(WebhookEvent.objects.get().outcome, "processed")

    def test_jeko_accepts_whole_fcfa_amounts_too(self):
        self.jeko_hook(self.ref_jeko, amount=10000)
        self.assertEqual(self.status_of(self.ref_jeko), "paid")

    def test_jeko_bad_signature_is_rejected_and_changes_nothing(self):
        res = self.jeko_hook(self.ref_jeko, sig="0" * 64)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(self.status_of(self.ref_jeko), "pending")
        self.assertFalse(WebhookEvent.objects.get().signature_valid)

    def test_jeko_missing_signature_is_rejected(self):
        raw = b"{}"
        self.assertEqual(self.client.post("/api/payments/webhooks/jeko/", data=raw, content_type="application/json").status_code, 401)

    def test_jeko_other_events_and_failures_are_acknowledged_but_ignored(self):
        self.assertEqual(self.jeko_hook(self.ref_jeko, event="TRANSACTION_FAILED", status="error").status_code, 200)
        self.assertEqual(self.jeko_hook(self.ref_jeko, status="pending").status_code, 200)
        self.assertEqual(self.status_of(self.ref_jeko), "pending")

    def test_jeko_unknown_reference_is_acknowledged(self):
        self.assertEqual(self.jeko_hook("DJZ-b999-deadbeef").status_code, 200)
        self.assertEqual(WebhookEvent.objects.get().outcome, "unknown")

    def test_jeko_wrong_amount_goes_to_review_and_the_booking_stays_unpaid(self):
        self.jeko_hook(self.ref_jeko, amount=5_000)  # 50 F au lieu de 10 000 F
        self.assertEqual(self.status_of(self.ref_jeko), "review")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, "unpaid")

    def test_wrong_currency_goes_to_review(self):
        self.jeko_hook(self.ref_jeko, currency="USD")
        self.assertEqual(self.status_of(self.ref_jeko), "review")

    def test_a_replayed_webhook_is_harmless(self):
        self.jeko_hook(self.ref_jeko)
        paid_at = Payment.objects.get().paid_at
        self.jeko_hook(self.ref_jeko)
        self.assertEqual(Payment.objects.get().paid_at, paid_at)
        self.assertEqual(Payment.objects.filter(status="paid").count(), 1)

    # --- Paystack ---
    def test_paystack_success(self):
        ref = client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": "card"}, format="json").json()["reference"]
        self.assertEqual(self.paystack_hook(ref).status_code, 200)
        self.assertEqual(self.status_of(ref), "paid")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, "paid")

    def test_paystack_bad_signature_and_wrong_amount(self):
        ref = client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": "card"}, format="json").json()["reference"]
        self.assertEqual(self.paystack_hook(ref, sig="abc").status_code, 401)
        self.assertEqual(self.paystack_hook(ref, sig="").status_code, 401)
        self.assertEqual(self.status_of(ref), "pending")
        self.paystack_hook(ref, amount=100)
        self.assertEqual(self.status_of(ref), "review")

    def test_paystack_ignores_other_events(self):
        ref = client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": "card"}, format="json").json()["reference"]
        self.assertEqual(self.paystack_hook(ref, event="charge.failed").status_code, 200)
        self.assertEqual(self.status_of(ref), "pending")

    def test_a_jeko_signature_does_not_validate_a_paystack_hook(self):
        ref = client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": "card"}, format="json").json()["reference"]
        raw = json.dumps({"event": "charge.success", "data": {"reference": ref, "amount": 1_000_000, "currency": "XOF"}}).encode()
        res = self.client.post("/api/payments/webhooks/paystack/", data=raw, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=jeko_sig(raw))
        self.assertEqual(res.status_code, 401)

    # --- cas particuliers ---
    def test_duo_booking_is_partial_until_both_have_paid(self):
        awa = make_member("Awa K.")
        booking, _, client = make_confirmed_booking(price=14000, kind="duo", partner=awa)
        ref_c = client_for(client).post("/api/payments/", {"purpose": "booking", "target": booking.id, "method": "wave"}, format="json").json()["reference"]
        ref_a = client_for(awa).post("/api/payments/", {"purpose": "booking", "target": booking.id, "method": "wave"}, format="json").json()["reference"]
        self.jeko_hook(ref_c, amount=700_000)
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, "partial")
        self.jeko_hook(ref_a, amount=700_000)
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, "paid")

    def test_paying_twice_flags_the_second_payment_for_refund(self):
        # deux pages de paiement ouvertes, les deux aboutissent
        first = self.ref_jeko
        second = client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": "card"}, format="json").json()["reference"]
        self.jeko_hook(first)
        self.paystack_hook(second)
        self.assertEqual(self.status_of(second), "duplicate")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, "paid")

    def test_class_seat_is_marked_paid(self):
        gym = make_gym()
        cls = GymClass.objects.create(gym=gym, name="Zumba", starts_at=timezone.now() + timedelta(days=2), capacity=5, price=2000)
        me = make_member("Olivier K.")
        seat = ClassBooking.objects.create(gym_class=cls, user=me)
        ref = client_for(me).post("/api/payments/", {"purpose": "class", "target": seat.id, "method": "wave"}, format="json").json()["reference"]
        self.jeko_hook(ref, amount=200_000)
        seat.refresh_from_db()
        self.assertTrue(seat.paid)
        self.assertIsNotNone(seat.paid_at)

    def test_serializers_expose_my_share_and_payment_state(self):
        before = client_for(self.client_user).get("/api/bookings/").json()[0]
        self.assertEqual((before["my_share"], before["paid_by_me"]), (10000, False))
        self.jeko_hook(self.ref_jeko)
        after = client_for(self.client_user).get("/api/bookings/").json()[0]
        self.assertEqual((after["payment_status"], after["paid_by_me"]), ("paid", True))
        self.assertIsNone(client_for(self.pro).get("/api/bookings/?role=pro").json()[0]["my_share"])


@override_settings(**KEYS)
class VerifyTests(APITestCase):
    """Repli quand le webhook tarde : le retour sur le site déclenche une vérification auprès du prestataire."""

    def setUp(self):
        self.net = Network()
        patcher = patch("requests.request", side_effect=self.net)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.booking, self.pro, self.client_user = make_confirmed_booking()

    def start(self, method):
        return client_for(self.client_user).post("/api/payments/", {"purpose": "booking", "target": self.booking.id, "method": method}, format="json").json()["reference"]

    def verify(self, ref, user=None):
        return client_for(user or self.client_user).post(f"/api/payments/{ref}/verify/")

    def test_paystack_verification_completes_the_payment(self):
        ref = self.start("card")
        self.net.paystack_verify = {"status": "success", "amount": 1_000_000, "currency": "XOF", "reference": ref, "paid_at": "2026-11-16T09:00:00.000Z"}
        res = self.verify(ref)
        self.assertEqual(res.json()["status"], "paid")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, "paid")

    def test_an_unfinished_payment_stays_pending(self):
        self.assertEqual(self.verify(self.start("card")).json()["status"], "pending")

    def test_jeko_verification(self):
        ref = self.start("wave")
        self.net.jeko_status = {"status": "success", "transaction": {"amount": {"amount": 1_000_000, "currency": "XOF"}}}
        self.assertEqual(self.verify(ref).json()["status"], "paid")

    def test_a_wrong_amount_from_the_provider_is_not_accepted(self):
        ref = self.start("card")
        self.net.paystack_verify = {"status": "success", "amount": 100, "currency": "XOF"}
        self.assertEqual(self.verify(ref).json()["status"], "review")

    def test_provider_outage_returns_the_known_state(self):
        ref = self.start("card")
        self.net.paystack_down = True
        res = self.verify(ref)
        self.assertEqual((res.status_code, res.json()["status"]), (200, "pending"))

    def test_only_the_payer_can_verify_or_read_a_payment(self):
        ref = self.start("card")
        stranger = make_member("Intrus")
        self.assertEqual(self.verify(ref, user=stranger).status_code, 404)
        self.assertEqual(client_for(stranger).get(f"/api/payments/{ref}/").status_code, 404)
        self.assertEqual(client_for(self.client_user).get(f"/api/payments/{ref}/").json()["amount"], 10000)
