from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.chat.models import Conversation
from apps.feed.models import Post

from .models import Meetup
from .services import punctuality


def in_hours(h):
    return (timezone.now() + timedelta(hours=h)).isoformat()


class MeetupFlowTests(APITestCase):
    def setUp(self):
        self.gym = make_gym()
        self.me = make_member("Olivier K.", gym=self.gym)
        self.awa = make_member("Awa K.", gym=self.gym)

    def propose(self, hours=24):
        return client_for(self.me).post(
            "/api/meetups/", {"partner": self.awa.id, "starts_at": in_hours(hours), "gym": self.gym.id}, format="json"
        )

    def test_proposing_creates_a_pending_meetup_and_a_conversation(self):
        res = self.propose()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "pending")
        self.assertEqual(Conversation.objects.count(), 1)

    def test_a_meetup_cannot_be_in_the_past_or_with_oneself(self):
        past = client_for(self.me).post(
            "/api/meetups/", {"partner": self.awa.id, "starts_at": in_hours(-1)}, format="json"
        )
        self.assertEqual(past.status_code, 400)
        alone = client_for(self.me).post(
            "/api/meetups/", {"partner": self.me.id, "starts_at": in_hours(5)}, format="json"
        )
        self.assertEqual(alone.status_code, 400)

    def test_only_the_invited_person_can_answer(self):
        mid = self.propose().json()["id"]
        wrong = client_for(self.me).post(f"/api/meetups/{mid}/respond/", {"accept": True}, format="json")
        self.assertEqual(wrong.status_code, 400)
        ok = client_for(self.awa).post(f"/api/meetups/{mid}/respond/", {"accept": True}, format="json")
        self.assertEqual(ok.json()["status"], "confirmed")
        twice = client_for(self.awa).post(f"/api/meetups/{mid}/respond/", {"accept": False}, format="json")
        self.assertEqual(twice.status_code, 400)

    def test_strangers_get_a_404(self):
        mid = self.propose().json()["id"]
        stranger = make_member("Intrus", gym=self.gym)
        res = client_for(stranger).post(f"/api/meetups/{mid}/cancel/")
        self.assertEqual(res.status_code, 404)

    def test_both_arrivals_complete_the_meetup(self):
        m = Meetup.objects.create(
            organizer=self.me, partner=self.awa, starts_at=timezone.now() + timedelta(minutes=5), status="confirmed"
        )
        r1 = client_for(self.me).post(f"/api/meetups/{m.id}/arrive/")
        self.assertEqual(r1.json()["status"], "confirmed")
        r2 = client_for(self.awa).post(f"/api/meetups/{m.id}/arrive/")
        self.assertEqual(r2.json()["status"], "done")

    def test_arrival_outside_the_window_is_refused(self):
        m = Meetup.objects.create(
            organizer=self.me, partner=self.awa, starts_at=timezone.now() + timedelta(days=2), status="confirmed"
        )
        res = client_for(self.me).post(f"/api/meetups/{m.id}/arrive/")
        self.assertEqual(res.status_code, 400)

    def test_arrival_needs_a_confirmed_meetup(self):
        m = Meetup.objects.create(organizer=self.me, partner=self.awa, starts_at=timezone.now())
        self.assertEqual(client_for(self.me).post(f"/api/meetups/{m.id}/arrive/").status_code, 400)

    def test_punctuality_needs_three_done_meetups(self):
        base = timezone.now() - timedelta(days=10)
        for i in range(2):
            Meetup.objects.create(
                organizer=self.me, partner=self.awa, starts_at=base + timedelta(days=i), status="done",
                organizer_arrived_at=base + timedelta(days=i), partner_arrived_at=base + timedelta(days=i),
            )
        self.assertIsNone(punctuality(self.me))
        Meetup.objects.create(
            organizer=self.me, partner=self.awa, starts_at=base + timedelta(days=5), status="done",
            organizer_arrived_at=base + timedelta(days=5, minutes=30), partner_arrived_at=base + timedelta(days=5),
        )
        # 2 séances sur 3 à l'heure pour moi (la troisième avec 30 min de retard)
        self.assertEqual(punctuality(self.me), round(5 * 2 / 3, 1))
        self.assertEqual(punctuality(self.awa), 5.0)

    def test_listing_only_shows_my_meetups(self):
        self.propose()
        other = make_member("Autre", gym=self.gym)
        self.assertEqual(len(client_for(other).get("/api/meetups/").json()), 0)
        self.assertEqual(len(client_for(self.awa).get("/api/meetups/").json()), 1)


class ChatTests(APITestCase):
    def setUp(self):
        self.a = make_member("Olivier K.")
        self.b = make_member("Awa K.")
        conv = client_for(self.a).post("/api/conversations/start/", {"user": self.b.id}, format="json")
        self.assertEqual(conv.status_code, 201)
        self.cid = conv.json()["id"]

    def test_starting_twice_returns_the_same_conversation(self):
        again = client_for(self.b).post("/api/conversations/start/", {"user": self.a.id}, format="json")
        self.assertEqual(again.json()["id"], self.cid)

    def test_messages_and_unread_counts(self):
        client_for(self.a).post(f"/api/conversations/{self.cid}/messages/", {"body": "Salut"}, format="json")
        client_for(self.a).post(f"/api/conversations/{self.cid}/messages/", {"body": "On y va ?"}, format="json")
        listing = client_for(self.b).get("/api/conversations/").json()
        self.assertEqual(listing[0]["unread"], 2)
        self.assertEqual(listing[0]["last_message"], "On y va ?")
        msgs = client_for(self.b).get(f"/api/conversations/{self.cid}/messages/").json()
        self.assertEqual([m["body"] for m in msgs], ["Salut", "On y va ?"])
        self.assertEqual(client_for(self.b).get("/api/conversations/").json()[0]["unread"], 0)

    def test_polling_returns_only_new_messages(self):
        first = client_for(self.a).post(f"/api/conversations/{self.cid}/messages/", {"body": "1"}, format="json").json()
        client_for(self.a).post(f"/api/conversations/{self.cid}/messages/", {"body": "2"}, format="json")
        res = client_for(self.b).get(f"/api/conversations/{self.cid}/messages/?after={first['id']}").json()
        self.assertEqual([m["body"] for m in res], ["2"])

    def test_empty_and_oversized_messages_are_refused(self):
        url = f"/api/conversations/{self.cid}/messages/"
        self.assertEqual(client_for(self.a).post(url, {"body": "  "}, format="json").status_code, 400)
        self.assertEqual(client_for(self.a).post(url, {"body": "x" * 1001}, format="json").status_code, 400)

    def test_outsiders_cannot_read_or_write(self):
        outsider = make_member("Intrus")
        url = f"/api/conversations/{self.cid}/messages/"
        self.assertEqual(client_for(outsider).get(url).status_code, 404)
        self.assertEqual(client_for(outsider).post(url, {"body": "hey"}, format="json").status_code, 404)

    def test_cannot_message_oneself(self):
        res = client_for(self.a).post("/api/conversations/start/", {"user": self.a.id}, format="json")
        self.assertEqual(res.status_code, 400)


class FeedTests(APITestCase):
    def setUp(self):
        self.gym = make_gym()
        self.koffi = make_member("Koffi Y.", gym=self.gym)
        self.me = make_member("Olivier K.", gym=self.gym)

    def test_buddy_post_needs_a_future_time(self):
        c = client_for(self.koffi)
        bad = c.post("/api/posts/", {"kind": "buddy", "body": "Qui vient ?"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = c.post("/api/posts/", {"kind": "buddy", "body": "Qui vient ?", "starts_at": in_hours(12)}, format="json")
        self.assertEqual(ok.status_code, 201)

    def test_text_post_ignores_a_time(self):
        res = client_for(self.koffi).post(
            "/api/posts/", {"kind": "text", "body": "Bonne séance", "starts_at": in_hours(3)}, format="json"
        )
        self.assertIsNone(res.json()["starts_at"])

    def test_joining_a_buddy_post_creates_a_pending_meetup(self):
        post = Post.objects.create(
            author=self.koffi, kind="buddy", body="Qui vient ?", gym=self.gym,
            starts_at=timezone.now() + timedelta(hours=12),
        )
        res = client_for(self.me).post(f"/api/posts/{post.id}/join/")
        self.assertEqual(res.status_code, 201)
        m = Meetup.objects.get()
        self.assertEqual((m.organizer, m.partner, m.status), (self.me, self.koffi, "pending"))

    def test_cannot_join_own_or_expired_posts(self):
        own = Post.objects.create(author=self.me, kind="buddy", body="x", starts_at=timezone.now() + timedelta(hours=2))
        self.assertEqual(client_for(self.me).post(f"/api/posts/{own.id}/join/").status_code, 400)
        old = Post.objects.create(author=self.koffi, kind="buddy", body="x", starts_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(client_for(self.me).post(f"/api/posts/{old.id}/join/").status_code, 400)

    def test_pros_filter_only_lists_verified_pros(self):
        coach = make_member("Coach Serge")
        coach.pro_type, coach.pro_verified = "coach", True
        coach.save()
        fake = make_member("Faux nutritionniste")
        fake.pro_type = "nutrition"
        fake.save()
        for u, text in [(coach, "Squat"), (fake, "Régime miracle"), (self.koffi, "Salut")]:
            Post.objects.create(author=u, body=text)
        res = client_for(self.me).get("/api/posts/?pros=1").json()
        self.assertEqual([p["body"] for p in res["results"]], ["Squat"])
