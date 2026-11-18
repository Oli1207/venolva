from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.backoffice.tests import jwt_client, make_staff, set_cfg
from apps.feed.models import Post
from apps.market.models import Listing
from apps.notifications.models import Notification

from . import services
from .models import Feature


def verified_pro(name="Coach"):
    u = make_member(name)
    u.pro_type, u.pro_verified = "coach", True
    u.save()
    return u


class FeatureFlowTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.adm = jwt_client(self.staff)
        self.pro = verified_pro()
        self.c = client_for(self.pro)
        self.post = Post.objects.create(author=self.pro, kind="article", title="Titre article", body="x" * 150)

    def ask(self, **kw):
        body = {"kind": "post", "target": self.post.id, "days": 3}
        body.update(kw)
        return self.c.post("/api/features/", body, format="json")

    def test_request_approve_goes_live_and_notifies(self):
        res = self.ask()
        self.assertEqual(res.status_code, 201)
        fid = res.json()["id"]
        self.assertEqual(self.c.get("/api/features/live/").json(), [])
        self.assertEqual(self.adm.post(f"/api/admin/features/{fid}/approve/").status_code, 200)
        live = self.c.get("/api/features/live/").json()
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["label"], "À la une")
        self.assertEqual(live[0]["link"], f"/publication/{self.post.id}")
        self.assertTrue(Notification.objects.filter(user=self.pro, kind="feature_approved").exists())

    def test_only_own_content_and_valid_durations(self):
        other = make_member("Autre")
        foreign = Post.objects.create(author=other, body="a")
        self.assertEqual(self.ask(target=foreign.id).status_code, 400)
        self.assertEqual(self.ask(days=0).status_code, 400)
        self.assertEqual(self.ask(days=999).status_code, 400)
        self.assertEqual(self.ask(days=True).status_code, 400)
        self.assertEqual(self.ask(kind="gym", target=1).status_code, 400)

    def test_no_double_request_for_the_same_content(self):
        self.assertEqual(self.ask().status_code, 201)
        self.assertEqual(self.ask().status_code, 400)

    def test_members_cannot_feature_a_pro_profile_or_a_sold_listing(self):
        plain = make_member("Simple")
        res = client_for(plain).post("/api/features/", {"kind": "pro", "target": plain.id, "days": 3}, format="json")
        self.assertEqual(res.status_code, 400)
        item = Listing.objects.create(seller=plain, title="Haltères", price=5000, category="weights", status="sold")
        res = client_for(plain).post("/api/features/", {"kind": "listing", "target": item.id, "days": 3}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_slots_are_limited_and_free_again_after_ending(self):
        set_cfg(featured_slots=1)
        a = services.create_direct(self.staff, "pro", self.pro.id, 5)
        other = verified_pro("Coach 2")
        req = services.request_feature(other, "pro", other.id, 5)
        with self.assertRaises(services.PromoError):
            services.approve(req, self.staff)
        services.end_now(a, self.staff)
        services.approve(req, self.staff)
        self.assertEqual(Feature.objects.get(pk=req.pk).status, "approved")

    def test_reject_and_double_decision(self):
        fid = self.ask().json()["id"]
        self.assertEqual(self.adm.post(f"/api/admin/features/{fid}/reject/", {"note": "Hors sujet"}, format="json").status_code, 200)
        self.assertEqual(self.adm.post(f"/api/admin/features/{fid}/approve/").status_code, 400)
        self.assertTrue(Notification.objects.filter(user=self.pro, kind="feature_rejected").exists())

    def test_members_cannot_use_admin_endpoints(self):
        fid = self.ask().json()["id"]
        self.assertEqual(self.c.post(f"/api/admin/features/{fid}/approve/").status_code, 403)

    def test_views_and_clicks_count_once_per_member_per_day(self):
        f = services.create_direct(self.staff, "pro", self.pro.id, 5)
        fan = client_for(make_member("Fan"))
        for _ in range(3):
            fan.post(f"/api/features/{f.id}/seen/")
            fan.post(f"/api/features/{f.id}/click/")
        f.refresh_from_db()
        self.assertEqual((f.views, f.clicks), (1, 1))
        client_for(make_member("Fan 2")).post(f"/api/features/{f.id}/seen/")
        f.refresh_from_db()
        self.assertEqual(f.views, 2)

    def test_scope_commune_limits_who_sees_it(self):
        f = services.create_direct(self.staff, "pro", self.pro.id, 5, commune="Yopougon")
        cocody = client_for(make_member("A", commune="Cocody"))
        yop = client_for(make_member("B", commune="Yopougon"))
        self.assertEqual(cocody.get("/api/features/live/").json(), [])
        self.assertEqual(len(yop.get("/api/features/live/").json()), 1)
        self.assertEqual(f.scope_commune, "Yopougon")

    def test_expired_features_disappear(self):
        f = services.create_direct(self.staff, "pro", self.pro.id, 1)
        Feature.objects.filter(pk=f.pk).update(ends_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(client_for(make_member("Z")).get("/api/features/live/").json(), [])

    def test_my_features_lists_stats(self):
        self.ask()
        data = self.c.get("/api/features/mine/").json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["status"], "pending")

    def test_direct_sponsored_by_admin(self):
        res = self.adm.post("/api/admin/features/", {"kind": "pro", "target": self.pro.id, "days": 4, "sponsored": True}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.c.get("/api/features/live/").json()[0]["label"], "Sponsorisé")


class FeaturedFirstTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.me = make_member("Moi")
        self.c = client_for(self.me)

    def test_featured_pro_is_flagged_and_first(self):
        a, b = verified_pro("Aaa"), verified_pro("Zzz")
        for p in (a, b):
            from apps.pros.models import ProProfile, Service

            ProProfile.objects.create(user=p, status="approved", speciality="x")
            Service.objects.create(owner=p, name="Séance", price=5000, duration_min=60)
        services.create_direct(self.staff, "pro", b.id, 3)
        rows = self.c.get("/api/pros/").json()
        self.assertEqual([r["person"]["id"] for r in rows][0], b.id)
        self.assertTrue(rows[0]["featured"])
        self.assertFalse(rows[1]["featured"])

    def test_featured_gym_and_listing_come_first(self):
        g1, g2 = make_gym("Alpha"), make_gym("Zeta")
        services.create_direct(self.staff, "gym", g2.id, 3)
        names = [g["name"] for g in self.c.get("/api/gyms/").json()]
        self.assertEqual(names[0], "Zeta")
        seller = make_member("Vendeur")
        old = Listing.objects.create(seller=seller, title="Ancienne", price=1000, category="weights")
        Listing.objects.create(seller=seller, title="Récente", price=1000, category="weights")
        services.create_direct(self.staff, "listing", old.id, 3)
        titles = [l["title"] for l in self.c.get("/api/listings/").json()["results"]]
        self.assertEqual(titles[0], "Ancienne")
        self.assertEqual(g1.name, "Alpha")
