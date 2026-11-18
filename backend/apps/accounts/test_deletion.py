from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.backoffice.tests import jwt_client, make_staff
from apps.feed.models import Post
from apps.market.models import Listing
from apps.meetups.models import Meetup
from apps.payments.models import Payment

from .models import User
from .testing import client_for, make_gym, make_member


class DeleteAccountTests(APITestCase):
    def setUp(self):
        self.me = make_member("Moi")
        self.c = jwt_client(self.me)

    def delete(self, confirm="SUPPRIMER"):
        return self.c.delete("/api/auth/me/", {"confirm": confirm}, format="json")

    def test_requires_explicit_confirmation(self):
        self.assertEqual(self.delete("oui").status_code, 400)
        self.me.refresh_from_db()
        self.assertTrue(self.me.is_active)

    def test_anonymizes_and_locks_the_account(self):
        Post.objects.create(author=self.me, body="salut")
        Listing.objects.create(seller=self.me, title="Haltères", price=5000, category="weights")
        phone = self.me.phone
        self.assertEqual(self.delete().status_code, 204)
        self.me.refresh_from_db()
        self.assertFalse(self.me.is_active)
        self.assertEqual(self.me.display_name, "Ancien membre")
        self.assertNotEqual(self.me.phone, phone)
        self.assertFalse(self.me.has_usable_password())
        self.assertFalse(Post.objects.filter(author=self.me).exists())
        self.assertFalse(Listing.objects.filter(seller=self.me).exists())
        self.assertFalse(self.me.profile.visible)
        self.assertEqual(self.c.get("/api/auth/me/").status_code, 401)  # le jeton ne marche plus

    def test_the_old_phone_number_can_register_again(self):
        phone = self.me.phone
        self.delete()
        again = User.objects.create_user(phone=phone, display_name="Nouveau")
        self.assertNotEqual(again.pk, self.me.pk)

    def test_blocked_by_an_upcoming_meetup(self):
        other = make_member("Awa")
        Meetup.objects.create(organizer=self.me, partner=other, starts_at=timezone.now() + timedelta(days=1))
        res = self.delete()
        self.assertEqual(res.status_code, 409)
        self.assertIn("séances", res.json()["detail"])

    def test_blocked_by_money_owed_and_by_owning_a_gym(self):
        client = make_member("Client")
        Payment.objects.create(user=client, payee=self.me, purpose="booking", target_id=1, amount=10000, fee=1000, net=9000, status="paid", reference="r1", provider="paystack", method="wave")
        self.assertEqual(self.delete().status_code, 409)
        Payment.objects.all().delete()
        gym = make_gym()
        gym.owner = self.me
        gym.save()
        self.assertEqual(self.delete().status_code, 409)

    def test_staff_cannot_self_delete(self):
        staff = make_staff()
        res = jwt_client(staff).delete("/api/auth/me/", {"confirm": "SUPPRIMER"}, format="json")
        self.assertEqual(res.status_code, 409)

    def test_requires_login(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().delete("/api/auth/me/", {"confirm": "SUPPRIMER"}, format="json").status_code, 401)
        self.assertIsNotNone(client_for(self.me))
