from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.accounts.testing import client_for, make_gym, make_member
from apps.feed.models import Post
from apps.market.models import Listing
from apps.pros.models import Booking, Service

from .models import AuditLog
from .tests import jwt_client, make_staff


class AdminContentTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.adm = jwt_client(self.staff)
        self.member = make_member("Awa K.")
        self.c = client_for(self.member)

    def test_every_new_route_is_staff_only(self):
        zero = "00000000-0000-0000-0000-000000000001"
        for method, url in (
            ("get", "/api/admin/posts/"), ("post", f"/api/admin/posts/{zero}/hide/"), ("get", "/api/admin/listings/"),
            ("post", f"/api/admin/listings/{zero}/hide/"), ("get", "/api/admin/bookings/"), ("post", "/api/admin/users/create/"), ("post", "/api/admin/gyms/create/"),
        ):
            self.assertEqual(getattr(self.c, method)(url).status_code, 403, url)

    def test_create_a_member_by_email_and_refuse_duplicates(self):
        res = self.adm.post("/api/admin/users/create/", {"email": " Nouvelle@Exemple.TEST ", "display_name": "Nouvelle N.", "commune": "Marcory"}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(User.objects.get(email="nouvelle@exemple.test").display_name, "Nouvelle N.")
        self.assertEqual(self.adm.post("/api/admin/users/create/", {"email": "nouvelle@exemple.test"}, format="json").status_code, 400)
        self.assertEqual(self.adm.post("/api/admin/users/create/", {"email": "pas-un-email"}, format="json").status_code, 400)
        self.assertTrue(AuditLog.objects.filter(action="user.create").exists())

    def test_fix_an_old_account_with_an_email_and_a_name(self):
        old = User.objects.create_user(phone="0700001234", display_name="Ancien")
        res = self.adm.patch(f"/api/admin/users/{old.id}/", {"email": "ancien@exemple.test", "display_name": "Ancien A.", "commune": "Cocody"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        old.refresh_from_db()
        self.assertEqual((old.email, old.display_name, old.commune), ("ancien@exemple.test", "Ancien A.", "Cocody"))
        clash = self.adm.patch(f"/api/admin/users/{old.id}/", {"email": self.member.email}, format="json")
        self.assertEqual(clash.status_code, 400)
        self.assertEqual(self.adm.patch(f"/api/admin/users/{old.id}/", {"email": "oups"}, format="json").status_code, 400)

    def test_create_and_edit_a_gym(self):
        res = self.adm.post("/api/admin/gyms/create/", {"name": "Fit Zone", "commune": "Yopougon", "address": "Rue 12"}, format="json")
        self.assertEqual(res.status_code, 201)
        gid = res.json()["id"]
        self.assertEqual(self.adm.post("/api/admin/gyms/create/", {"name": "", "commune": "X"}, format="json").status_code, 400)
        res = self.adm.patch(f"/api/admin/gyms/{gid}/", {"name": "Fit Zone Plus", "address": "Rue 13"}, format="json")
        self.assertEqual((res.status_code, res.json()["name"], res.json()["address"]), (200, "Fit Zone Plus", "Rue 13"))
        self.assertEqual(self.adm.patch(f"/api/admin/gyms/{gid}/", {"name": " "}, format="json").status_code, 400)
        self.assertEqual(self.adm.patch(f"/api/admin/gyms/{gid}/", {"verified": True}, format="json").status_code, 200)  # l'existant marche toujours

    def test_posts_list_filter_hide_show_delete(self):
        ok = Post.objects.create(author=self.member, body="Bonjour tout le monde")
        bad = Post.objects.create(author=self.member, body="Arnaque crypto")
        res = self.adm.get("/api/admin/posts/?q=crypto").json()
        self.assertEqual([r["id"] for r in res["results"]], [str(bad.id)])
        self.assertEqual(self.adm.post(f"/api/admin/posts/{bad.id}/hide/").status_code, 200)
        bad.refresh_from_db()
        self.assertTrue(bad.hidden)
        self.assertEqual(self.adm.get("/api/admin/posts/?hidden=1").json()["count"], 1)
        self.assertEqual(self.adm.post(f"/api/admin/posts/{bad.id}/show/").status_code, 200)
        self.assertEqual(self.adm.post(f"/api/admin/posts/{bad.id}/delete/").status_code, 200)
        self.assertFalse(Post.objects.filter(pk=bad.pk).exists())
        self.assertTrue(Post.objects.filter(pk=ok.pk).exists())
        self.assertEqual(self.adm.post(f"/api/admin/posts/{ok.id}/explode/").status_code, 404)

    def test_listings_hide_and_restore(self):
        item = Listing.objects.create(seller=self.member, title="Haltères 10 kg", price=8000, category="weights")
        self.assertEqual(self.adm.get("/api/admin/listings/?q=halt").json()["count"], 1)
        self.assertEqual(self.adm.post(f"/api/admin/listings/{item.id}/hide/").json()["status"], "hidden")
        self.assertEqual(self.adm.get("/api/admin/listings/?status=hidden").json()["count"], 1)
        self.assertEqual(self.adm.post(f"/api/admin/listings/{item.id}/restore/").json()["status"], "active")

    def test_bookings_are_listed_for_support(self):
        pro = make_member("Coach")
        pro.pro_type, pro.pro_verified = "coach", True
        pro.save()
        svc = Service.objects.create(owner=pro, name="Séance", price=5000, duration_min=60)
        start = timezone.now() + timedelta(days=2)
        Booking.objects.create(service=svc, pro=pro, client=self.member, starts_at=start, ends_at=start + timedelta(hours=1), price_total=5000, price_client=5000)
        rows = self.adm.get("/api/admin/bookings/?q=coach").json()
        self.assertEqual(rows["count"], 1)
        self.assertEqual((rows["results"][0]["service"], rows["results"][0]["status"]), ("Séance", "pending"))
        self.assertEqual(self.adm.get("/api/admin/bookings/?status=done").json()["count"], 0)

    def test_dashboard_counts_the_new_queues(self):
        from apps.promo import services as promo
        from apps.safety.models import ContentReport

        post = Post.objects.create(author=self.member, body="x")
        ContentReport.objects.create(reporter=make_member("R"), kind="post", post=post, reason="scam")
        pro = make_member("Coach")
        pro.pro_type, pro.pro_verified = "coach", True
        pro.save()
        promo.request_feature(pro, "pro", pro.id, 3)
        d = self.adm.get("/api/admin/dashboard/").json()
        self.assertEqual((d["content_reports_open"], d["features_pending"]), (1, 1))
        self.assertIsNotNone(make_gym())
