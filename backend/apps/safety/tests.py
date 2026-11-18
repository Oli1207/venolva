from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.backoffice.tests import jwt_client, make_staff
from apps.chat.models import Conversation
from apps.feed.models import Post
from apps.notifications.models import Notification

from .models import Block, ContentReport


class BlockTests(APITestCase):
    def setUp(self):
        gym = make_gym()
        self.me = make_member("Moi", gym=gym)
        self.awa = make_member("Awa", gym=gym)
        self.c = client_for(self.me)

    def block(self):
        return self.c.post("/api/blocks/", {"user": self.awa.id}, format="json")

    def test_block_unblock_and_list(self):
        self.assertEqual(self.block().status_code, 201)
        self.assertEqual(self.block().status_code, 201)  # idempotent
        self.assertEqual(Block.objects.count(), 1)
        self.assertEqual(self.c.get("/api/blocks/").json()[0]["id"], self.awa.id)
        self.assertEqual(self.c.delete(f"/api/blocks/{self.awa.id}/").status_code, 204)
        self.assertEqual(Block.objects.count(), 0)

    def test_cannot_block_oneself_or_staff(self):
        self.assertEqual(self.c.post("/api/blocks/", {"user": self.me.id}, format="json").status_code, 400)
        staff = make_staff()
        self.assertEqual(self.c.post("/api/blocks/", {"user": staff.id}, format="json").status_code, 400)

    def test_blocked_member_disappears_from_matches_and_profile_both_ways(self):
        self.assertIn(self.awa.id, [m["id"] for m in self.c.get("/api/matches/?min=0").json()])
        self.block()
        self.assertNotIn(self.awa.id, [m["id"] for m in self.c.get("/api/matches/?min=0").json()])
        self.assertEqual(self.c.get(f"/api/members/{self.awa.id}/").status_code, 404)
        # et dans l'autre sens
        other = client_for(self.awa)
        self.assertNotIn(self.me.id, [m["id"] for m in other.get("/api/matches/?min=0").json()])
        self.assertEqual(other.get(f"/api/members/{self.me.id}/").status_code, 404)

    def test_blocking_stops_messages_and_meetups(self):
        conv = self.c.post("/api/conversations/start/", {"user": self.awa.id}, format="json").json()["id"]
        self.block()
        self.assertEqual(self.c.get("/api/conversations/").json(), [])
        self.assertEqual(self.c.post(f"/api/conversations/{conv}/messages/", {"body": "salut"}, format="json").status_code, 403)
        self.assertEqual(client_for(self.awa).post(f"/api/conversations/{conv}/messages/", {"body": "salut"}, format="json").status_code, 403)
        self.assertEqual(self.c.post("/api/conversations/start/", {"user": self.awa.id}, format="json").status_code, 400)
        res = self.c.post("/api/meetups/", {"partner": self.awa.id, "starts_at": (timezone.now() + timedelta(hours=5)).isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_blocked_author_posts_vanish_from_the_list_and_detail(self):
        p = Post.objects.create(author=self.awa, body="coucou")
        self.assertEqual(len(self.c.get("/api/posts/").json()["results"]), 1)
        self.block()
        self.assertEqual(self.c.get("/api/posts/").json()["results"], [])
        self.assertEqual(self.c.get(f"/api/posts/{p.id}/").status_code, 404)
        self.assertEqual(self.c.post(f"/api/posts/{p.id}/join/").status_code, 404 if p.kind != "buddy" else 400)


class ReportTests(APITestCase):
    def setUp(self):
        self.me = make_member("Moi")
        self.awa = make_member("Awa")
        self.post = Post.objects.create(author=self.awa, body="arnaque")
        self.c = client_for(self.me)
        self.staff = make_staff()
        self.adm = jwt_client(self.staff)

    def report(self, **kw):
        body = {"kind": "post", "target": self.post.id, "reason": "scam"}
        body.update(kw)
        return self.c.post("/api/content-reports/", body, format="json")

    def test_report_once_only_and_validates_input(self):
        self.assertEqual(self.report().status_code, 201)
        self.assertEqual(self.report().status_code, 400)
        self.assertEqual(self.report(reason="nimporte").status_code, 400)
        self.assertEqual(self.report(kind="user", target=self.me.id).status_code, 400)
        self.assertEqual(self.report(target=Post.objects.create(author=self.me, body="a").id).status_code, 400)

    def test_admin_lists_and_hides_a_post_then_siblings_close(self):
        self.report()
        client_for(make_member("Zoe")).post("/api/content-reports/", {"kind": "post", "target": self.post.id, "reason": "fake"}, format="json")
        rows = self.adm.get("/api/admin/content-reports/").json()["results"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["same_target_reports"], 2)
        self.assertEqual(self.adm.post(f"/api/admin/content-reports/{rows[0]['id']}/hide_post/").status_code, 200)
        self.post.refresh_from_db()
        self.assertTrue(self.post.hidden)
        self.assertEqual(ContentReport.objects.filter(handled=False).count(), 0)
        self.assertTrue(Notification.objects.filter(user=self.awa, kind="post_hidden").exists())
        self.assertEqual(self.c.get(f"/api/posts/{self.post.id}/").status_code, 404)

    def test_suspend_user_and_dismiss(self):
        self.report(kind="user", target=self.awa.id, reason="harassment")
        r = ContentReport.objects.get()
        self.assertEqual(self.adm.post(f"/api/admin/content-reports/{r.id}/suspend_user/").status_code, 200)
        self.awa.refresh_from_db()
        self.assertFalse(self.awa.is_active)
        self.assertEqual(self.adm.post(f"/api/admin/content-reports/{r.id}/dismiss/").status_code, 400)  # déjà traité

    def test_dismiss_changes_nothing(self):
        self.report()
        r = ContentReport.objects.get()
        self.adm.post(f"/api/admin/content-reports/{r.id}/dismiss/")
        self.post.refresh_from_db()
        self.assertFalse(self.post.hidden)
        self.assertEqual(self.adm.get("/api/admin/content-reports/?handled=1").json()["count"], 1)

    def test_staff_accounts_are_protected_and_members_locked_out(self):
        self.report(kind="user", target=self.staff.id, reason="other")
        r = ContentReport.objects.get()
        self.assertEqual(self.adm.post(f"/api/admin/content-reports/{r.id}/suspend_user/").status_code, 400)
        self.assertEqual(self.c.get("/api/admin/content-reports/").status_code, 403)


class NotificationTests(APITestCase):
    def setUp(self):
        gym = make_gym()
        self.me = make_member("Moi", gym=gym)
        self.awa = make_member("Awa", gym=gym)

    def test_meetup_proposal_notifies_the_partner_and_read_flow(self):
        client_for(self.me).post("/api/meetups/", {"partner": self.awa.id, "starts_at": (timezone.now() + timedelta(hours=5)).isoformat()}, format="json")
        c = client_for(self.awa)
        data = c.get("/api/notifications/").json()
        self.assertEqual(data["unread"], 1)
        self.assertEqual(data["results"][0]["kind"], "meetup_proposed")
        self.assertEqual(client_for(self.me).get("/api/notifications/").json()["unread"], 0)
        c.post("/api/notifications/read/", {"all": True}, format="json")
        self.assertEqual(c.get("/api/notifications/").json()["unread"], 0)

    def test_cannot_mark_someone_elses_notifications(self):
        n = Notification.objects.create(user=self.awa, kind="x", title="t")
        client_for(self.me).post("/api/notifications/read/", {"ids": [n.id]}, format="json")
        n.refresh_from_db()
        self.assertIsNone(n.read_at)

    def test_liking_a_post_notifies_the_author_but_not_oneself(self):
        p = Post.objects.create(author=self.awa, body="x")
        client_for(self.me).post(f"/api/posts/{p.id}/like/")
        client_for(self.awa).post(f"/api/posts/{p.id}/like/")
        self.assertEqual(Notification.objects.filter(user=self.awa, kind="post_liked").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.me).count(), 0)
