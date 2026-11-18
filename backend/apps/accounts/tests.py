from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import OtpCode, User, normalize_phone


class PhoneTests(SimpleTestCase):
    def test_formats_are_normalized(self):
        for raw in ["07 00 00 00 00", "0700000000", "+2250700000000", "002250700000000", "225 07 00 00 00 00"]:
            self.assertEqual(normalize_phone(raw), "+2250700000000", raw)

    def test_invalid_numbers_are_rejected(self):
        for raw in ["", "123", "+33612345678", "07 00 00 00", "abc"]:
            with self.assertRaises(ValidationError, msg=raw):
                normalize_phone(raw)


class OtpFlowTests(APITestCase):
    def setUp(self):
        cache.clear()

    def request_code(self, email="Awa@Exemple.test"):
        res = self.client.post("/api/auth/otp/request/", {"email": email}, format="json")
        self.assertEqual(res.status_code, 200)
        return res.json()["dev_code"]

    def test_login_creates_account_and_returns_tokens(self):
        code = self.request_code()
        res = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["created"])
        self.assertIn("access", body)
        self.assertEqual(body["user"]["email"], "awa@exemple.test")
        self.assertFalse(body["user"]["profile"]["onboarded"])

    def test_second_login_does_not_duplicate_the_account(self):
        for _ in range(2):
            code = self.request_code()
            res = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json")
            self.assertEqual(res.status_code, 200)
        self.assertEqual(User.objects.filter(email="awa@exemple.test").count(), 1)

    def test_wrong_code_is_refused(self):
        self.request_code()
        res = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": "000000"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_code_cannot_be_reused(self):
        code = self.request_code()
        self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json")
        again = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_new_request_invalidates_the_previous_code(self):
        old = self.request_code()
        new = self.request_code()
        res = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": old}, format="json")
        if old != new:
            self.assertEqual(res.status_code, 400)

    def test_expired_code_is_refused(self):
        code = self.request_code()
        OtpCode.objects.update(created_at=timezone.now() - timedelta(minutes=10))
        res = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_too_many_wrong_attempts_lock_the_code(self):
        code = self.request_code()
        for _ in range(5):
            self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": "999999"}, format="json")
        res = self.client.post("/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_a_number_cannot_be_flooded_with_codes(self):
        for _ in range(5):
            self.assertEqual(
                self.client.post("/api/auth/otp/request/", {"email": "Awa@Exemple.test"}, format="json").status_code, 200
            )
        sixth = self.client.post("/api/auth/otp/request/", {"email": "Awa@Exemple.test"}, format="json")
        self.assertEqual(sixth.status_code, 429)

    @override_settings(OTP_DEV_ECHO=False)
    def test_code_is_not_returned_in_production(self):
        res = self.client.post("/api/auth/otp/request/", {"email": "Awa@Exemple.test"}, format="json")
        self.assertNotIn("dev_code", res.json())

    def test_profile_update_validates_goals(self):
        code = self.request_code()
        tokens = self.client.post(
            "/api/auth/otp/verify/", {"email": "Awa@Exemple.test", "code": code}, format="json"
        ).json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        bad = self.client.patch("/api/auth/me/", {"profile": {"goals": ["a", "b", "c"]}}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.client.patch(
            "/api/auth/me/",
            {"display_name": "Olivier K.", "commune": "Cocody", "profile": {"goals": ["weight_loss"], "onboarded": True}},
            format="json",
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["initials"], "OK")
        self.assertTrue(ok.json()["profile"]["onboarded"])


class EmailDeliveryTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_the_code_is_sent_by_email(self):
        from django.core import mail

        res = self.client.post("/api/auth/otp/request/", {"email": " Awa@Exemple.TEST "}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["awa@exemple.test"])
        self.assertIn(res.json()["dev_code"], mail.outbox[0].subject)

    def test_invalid_addresses_are_refused(self):
        for bad in ("", "pas-un-email", "a@", "0700000001"):
            res = self.client.post("/api/auth/otp/request/", {"email": bad}, format="json")
            self.assertEqual(res.status_code, 400, bad)

    def test_a_mail_server_failure_returns_503_and_hides_details(self):
        from unittest import mock

        with mock.patch("apps.accounts.views.send_mail", side_effect=OSError("smtp secret host")):
            res = self.client.post("/api/auth/otp/request/", {"email": "awa@exemple.test"}, format="json")
        self.assertEqual(res.status_code, 503)
        self.assertNotIn("smtp", res.content.decode())

    def test_same_person_same_account_whatever_the_case(self):
        for addr in ("awa@exemple.test", "AWA@exemple.test"):
            code = self.client.post("/api/auth/otp/request/", {"email": addr}, format="json").json()["dev_code"]
            self.client.post("/api/auth/otp/verify/", {"email": addr, "code": code}, format="json")
        self.assertEqual(User.objects.filter(email="awa@exemple.test").count(), 1)

    def test_admin_can_find_accounts_by_email_or_phone(self):
        from .models import find_user

        u = User.objects.create_user(email="Zoe@Exemple.test", phone="0700000777")
        self.assertEqual(find_user("zoe@exemple.test"), u)
        self.assertEqual(find_user("07 00 00 07 77"), u)
        with self.assertRaises(User.DoesNotExist):
            find_user("inconnu@exemple.test")
