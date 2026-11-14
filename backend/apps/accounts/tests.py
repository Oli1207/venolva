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

    def request_code(self, phone="07 00 00 00 01"):
        res = self.client.post("/api/auth/otp/request/", {"phone": phone}, format="json")
        self.assertEqual(res.status_code, 200)
        return res.json()["dev_code"]

    def test_login_creates_account_and_returns_tokens(self):
        code = self.request_code()
        res = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["created"])
        self.assertIn("access", body)
        self.assertEqual(body["user"]["phone"], "+2250700000001")
        self.assertFalse(body["user"]["profile"]["onboarded"])

    def test_second_login_does_not_duplicate_the_account(self):
        for _ in range(2):
            code = self.request_code()
            res = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json")
            self.assertEqual(res.status_code, 200)
        self.assertEqual(User.objects.filter(phone="+2250700000001").count(), 1)

    def test_wrong_code_is_refused(self):
        self.request_code()
        res = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": "000000"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_code_cannot_be_reused(self):
        code = self.request_code()
        self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json")
        again = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_new_request_invalidates_the_previous_code(self):
        old = self.request_code()
        new = self.request_code()
        res = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": old}, format="json")
        if old != new:
            self.assertEqual(res.status_code, 400)

    def test_expired_code_is_refused(self):
        code = self.request_code()
        OtpCode.objects.update(created_at=timezone.now() - timedelta(minutes=10))
        res = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_too_many_wrong_attempts_lock_the_code(self):
        code = self.request_code()
        for _ in range(5):
            self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": "999999"}, format="json")
        res = self.client.post("/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_a_number_cannot_be_flooded_with_codes(self):
        for _ in range(5):
            self.assertEqual(
                self.client.post("/api/auth/otp/request/", {"phone": "0700000001"}, format="json").status_code, 200
            )
        sixth = self.client.post("/api/auth/otp/request/", {"phone": "0700000001"}, format="json")
        self.assertEqual(sixth.status_code, 429)

    @override_settings(OTP_DEV_ECHO=False)
    def test_code_is_not_returned_in_production(self):
        res = self.client.post("/api/auth/otp/request/", {"phone": "0700000001"}, format="json")
        self.assertNotIn("dev_code", res.json())

    def test_profile_update_validates_goals(self):
        code = self.request_code()
        tokens = self.client.post(
            "/api/auth/otp/verify/", {"phone": "0700000001", "code": code}, format="json"
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
