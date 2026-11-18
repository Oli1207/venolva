import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.backoffice.tests import make_staff
from apps.chat.models import Message
from apps.feed.models import Post

from .testing import client_for, make_gym, make_member


class UuidIdentifierTests(APITestCase):
    def setUp(self):
        self.gym = make_gym()
        self.me = make_member("Moi", gym=self.gym)
        self.awa = make_member("Awa", gym=self.gym)
        self.c = client_for(self.me)

    def test_ids_are_random_uuids_not_a_counter(self):
        ids = [make_member(f"M{i}").id for i in range(3)]
        for i in ids:
            self.assertEqual(i.version, 4)
        self.assertEqual(len(set(ids)), 3)
        body = self.c.get("/api/auth/me/").json()
        self.assertEqual(uuid.UUID(body["id"]), self.me.id)

    def test_malformed_ids_in_the_url_are_a_404_not_a_crash(self):
        for url in ("/api/members/12/", "/api/posts/abc/", "/api/gyms/1/", "/api/pros/x/"):
            self.assertEqual(self.c.get(url).status_code, 404, url)

    def test_malformed_ids_in_the_body_are_a_clean_400_or_404(self):
        for url, body in (
            ("/api/conversations/start/", {"user": "abc"}),
            ("/api/blocks/", {"user": 12}),
            ("/api/payments/", {"purpose": "booking", "target": "7", "method": "wave"}),
            ("/api/features/", {"kind": "pro", "target": "nope", "days": 3}),
            ("/api/content-reports/", {"kind": "post", "target": "1", "reason": "scam"}),
        ):
            res = self.c.post(url, body, format="json")
            self.assertIn(res.status_code, (400, 404), (url, res.status_code))

    def test_unknown_uuid_is_a_404(self):
        self.assertEqual(self.c.get(f"/api/members/{uuid.uuid4()}/").status_code, 404)
        self.assertEqual(self.c.get(f"/api/posts/{uuid.uuid4()}/").status_code, 404)

    def test_malformed_list_filters_are_ignored(self):
        self.assertEqual(self.c.get("/api/matches/?gym=abc&min=0").status_code, 200)
        self.assertEqual(self.c.get("/api/gyms/?commune=Cocody").status_code, 200)

    def test_message_polling_uses_the_date_of_the_last_seen_message(self):
        conv = self.c.post("/api/conversations/start/", {"user": str(self.awa.id)}, format="json").json()["id"]
        sent = []
        for i in range(3):
            sent.append(self.c.post(f"/api/conversations/{conv}/messages/", {"body": f"m{i}"}, format="json").json())
            Message.objects.filter(pk=sent[-1]["id"]).update(created_at=timezone.now() - timedelta(minutes=10 - i))
        everything = self.c.get(f"/api/conversations/{conv}/messages/").json()
        self.assertEqual([m["body"] for m in everything], ["m0", "m1", "m2"])
        later = self.c.get(f"/api/conversations/{conv}/messages/?after={sent[0]['id']}").json()
        self.assertEqual([m["body"] for m in later], ["m1", "m2"])
        self.assertEqual(self.c.get(f"/api/conversations/{conv}/messages/?after={sent[2]['id']}").json(), [])
        self.assertEqual(len(self.c.get(f"/api/conversations/{conv}/messages/?after=abc").json()), 3)  # curseur invalide : tout

    def test_notifications_and_feed_seen_ignore_junk_ids(self):
        post = Post.objects.create(author=self.awa, body="x")
        res = self.c.post("/api/feed/seen/", {"ids": [str(post.id), "12", "zz", True, None]}, format="json")
        self.assertEqual((res.status_code, res.json()["recorded"]), (200, 1))
        self.assertEqual(self.c.post("/api/notifications/read/", {"ids": ["1", "zz", 5]}, format="json").status_code, 200)

    def test_audit_log_keeps_uuid_details(self):
        from apps.backoffice.models import AuditLog, audit

        staff = make_staff()
        audit(staff, "test.action", "x", owner=self.me.id, ids=[self.awa.id])
        entry = AuditLog.objects.get(action="test.action")
        self.assertEqual(entry.detail["owner"], str(self.me.id))
