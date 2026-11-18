from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.backoffice.tests import make_staff
from apps.promo import services as promo
from apps.safety.models import Block

from . import ranking
from .models import Post, PostImpression
from .ranking import Signals, Weights, diversify, insert_boosts, rotate_boosts, score_post

W = Weights()


def mk(author, body="Une publication", hours_ago=1, **kw):
    p = Post.objects.create(author=author, body=body, **kw)
    Post.objects.filter(pk=p.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago))
    return Post.objects.get(pk=p.pk)


class ScoreTests(APITestCase):
    def test_a_fresh_post_beats_an_old_one(self):
        self.assertGreater(score_post(Signals(age_hours=1), W)[0], score_post(Signals(age_hours=72), W)[0])

    def test_half_life_halves_the_score(self):
        new, old = score_post(Signals(age_hours=0), W)[0], score_post(Signals(age_hours=W.half_life_hours), W)[0]
        self.assertAlmostEqual(old / new, 0.5, places=2)

    def test_local_pro_and_liked_posts_rise(self):
        base = score_post(Signals(age_hours=5), W)[0]
        self.assertGreater(score_post(Signals(age_hours=5, same_commune=True), W)[0], base)
        self.assertGreater(score_post(Signals(age_hours=5, is_pro=True), W)[0], base)
        self.assertGreater(score_post(Signals(age_hours=5, likes=10), W)[0], base)

    def test_likes_saturate(self):
        a = score_post(Signals(age_hours=5, likes=ranking.LIKE_SATURATION), W)[0]
        b = score_post(Signals(age_hours=5, likes=10_000), W)[0]
        self.assertAlmostEqual(a, b, places=6)

    def test_seen_posts_sink_but_not_my_own(self):
        base = score_post(Signals(age_hours=5), W)[0]
        self.assertLess(score_post(Signals(age_hours=5, seen=2), W)[0], base)
        self.assertEqual(score_post(Signals(age_hours=5, seen=2, is_mine=True), W)[0], base)

    def test_an_approaching_session_outranks_a_distant_one(self):
        near = score_post(Signals(age_hours=3, hours_to_start=5), W)[0]
        far = score_post(Signals(age_hours=3, hours_to_start=40), W)[0]
        self.assertGreater(near, far)

    def test_reasons_explain_the_score(self):
        _, reasons = score_post(Signals(age_hours=1, is_pro=True, same_commune=True), W)
        self.assertIn("pro validé", reasons)
        self.assertIn("proche de toi", reasons)


class AssemblyTests(APITestCase):
    def test_diversify_limits_one_author_per_page_without_losing_posts(self):
        items = [{"author_id": 1}] * 5 + [{"author_id": 2}] * 2
        out = diversify(items, 2)
        self.assertEqual(len(out), 7)
        self.assertEqual([i["author_id"] for i in out[:4]], [1, 1, 2, 2])

    def test_boosts_are_spaced_and_never_stacked_at_the_end(self):
        out = insert_boosts(list("abcdefghij"), ["B1", "B2"], 4)
        self.assertEqual(out.index("B1"), 3)
        self.assertEqual(out.index("B2"), 7)
        self.assertEqual(insert_boosts(list("ab"), ["B"], 4), ["a", "b"])
        self.assertEqual(insert_boosts(list("abcdef"), ["B"], 0), list("abcdef"))

    def test_rotation_puts_the_least_seen_first(self):
        import uuid

        class F:
            def __init__(self, views):
                self.id, self.views = uuid.uuid4(), views

        fs = [F(50), F(3), F(20)]
        self.assertEqual(rotate_boosts(fs, uuid.uuid4(), timezone.localdate())[0].views, 3)


class FeedApiTests(APITestCase):
    def setUp(self):
        self.gym = make_gym()
        self.me = make_member("Moi", gym=self.gym)
        self.awa = make_member("Awa", gym=self.gym)
        self.far = make_member("Loin", commune="Yopougon")
        self.c = client_for(self.me)

    def feed(self, qs=""):
        return self.c.get(f"/api/feed/{qs}").json()

    def post_ids(self, data):
        return [r["post"]["id"] for r in data["results"] if r["type"] == "post"]

    def test_local_post_comes_before_a_slightly_fresher_distant_one(self):
        local = mk(self.awa, hours_ago=3)
        distant = mk(self.far, hours_ago=2)
        ids = self.post_ids(self.feed())
        self.assertLess(ids.index(str(local.id)), ids.index(str(distant.id)))

    def test_blocked_hidden_and_expired_posts_are_not_shown(self):
        blocked = mk(self.far, "bloqué")
        Block.objects.create(blocker=self.me, blocked=self.far)
        hidden = mk(self.awa, "masqué", hidden=True)
        past = mk(self.awa, "passée", kind="buddy", starts_at=timezone.now() - timedelta(hours=1))
        ok = mk(self.awa, "visible")
        ids = self.post_ids(self.feed())
        self.assertEqual(ids, [str(ok.id)])
        self.assertNotIn(str(blocked.id), ids)
        self.assertNotIn(str(hidden.id), ids)
        self.assertNotIn(str(past.id), ids)

    def test_pagination_is_stable_and_complete(self):
        for i in range(30):
            mk(make_member(f"M{i}"), f"p{i}", hours_ago=i + 1)
        first = self.feed("?size=10")
        second = self.feed(f"?size=10&cursor={first['next']}")
        third = self.feed(f"?size=10&cursor={second['next']}")
        seen = self.post_ids(first) + self.post_ids(second) + self.post_ids(third)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), 30)
        self.assertIsNone(third["next"])

    def test_bad_cursor_does_not_crash(self):
        mk(self.awa)
        self.assertEqual(self.c.get("/api/feed/?cursor=zzz").status_code, 200)

    def test_seen_posts_are_pushed_down(self):
        a = mk(self.awa, "a", hours_ago=2)
        b = mk(self.awa, "b", hours_ago=3)
        self.assertEqual(self.post_ids(self.feed()), [str(a.id), str(b.id)])
        for _ in range(3):
            self.assertEqual(self.c.post("/api/feed/seen/", {"ids": [a.id]}, format="json").status_code, 200)
        self.assertEqual(self.post_ids(self.feed()), [str(b.id), str(a.id)])
        self.assertEqual(PostImpression.objects.get(user=self.me, post=a).seen, 3)

    def test_own_posts_are_not_recorded_as_seen(self):
        mine = mk(self.me)
        self.c.post("/api/feed/seen/", {"ids": [mine.id]}, format="json")
        self.assertFalse(PostImpression.objects.exists())

    def test_likes_toggle_and_count(self):
        p = mk(self.awa)
        self.assertEqual(self.c.post(f"/api/posts/{p.id}/like/").json(), {"likes": 1, "liked": True})
        self.assertEqual(self.c.post(f"/api/posts/{p.id}/like/").json()["likes"], 1)  # idempotent
        self.assertTrue(self.feed()["results"][0]["post"]["liked"])
        self.assertEqual(self.c.delete(f"/api/posts/{p.id}/like/").json(), {"likes": 0, "liked": False})

    def test_cannot_like_a_post_of_someone_who_blocked_me(self):
        p = mk(self.far)
        Block.objects.create(blocker=self.far, blocked=self.me)
        self.assertEqual(self.c.post(f"/api/posts/{p.id}/like/").status_code, 404)

    def test_debug_scores_only_for_staff(self):
        mk(self.awa)
        self.assertNotIn("score", self.feed("?debug=1")["results"][0])
        data = client_for(make_staff()).get("/api/feed/?debug=1").json()
        self.assertIn("score", data["results"][0])
        self.assertTrue(data["results"][0]["reasons"])


class BoostTests(APITestCase):
    def setUp(self):
        self.me = make_member("Moi")
        self.pro = make_member("Coach")
        self.pro.pro_type, self.pro.pro_verified = "coach", True
        self.pro.save()
        self.staff = make_staff()
        self.c = client_for(self.me)
        for i in range(8):
            mk(make_member(f"A{i}"), f"p{i}", hours_ago=i + 1)

    def feed(self):
        return self.c.get("/api/feed/?size=30").json()["results"]

    def types(self):
        return [r["type"] for r in self.feed()]

    def test_a_featured_post_is_inserted_once_at_the_configured_spacing(self):
        art = mk(self.pro, "x" * 150, kind="article", title="Titre article", hours_ago=2)
        promo.create_direct(self.staff, "post", art.id, 3)
        types = self.types()
        self.assertEqual(types.count("feature"), 1)
        self.assertEqual(types.index("feature"), 5)  # feed_boost_every = 6
        ids = [r["post"]["id"] for r in self.feed() if r["type"] == "post"]
        self.assertNotIn(str(art.id), ids)  # pas en double

    def test_a_clicked_feature_stops_appearing_that_day(self):
        f = promo.create_direct(self.staff, "pro", self.pro.id, 3)
        self.assertEqual(self.types().count("feature"), 1)
        self.c.post(f"/api/features/{f.id}/click/")
        self.assertEqual(self.types().count("feature"), 0)

    def test_no_feature_from_a_blocked_author(self):
        promo.create_direct(self.staff, "pro", self.pro.id, 3)
        Block.objects.create(blocker=self.me, blocked=self.pro)
        self.assertEqual(self.types().count("feature"), 0)

    def test_filtered_views_have_no_ads(self):
        promo.create_direct(self.staff, "pro", self.pro.id, 3)
        types = [r["type"] for r in self.c.get("/api/feed/?kind=text").json()["results"]]
        self.assertNotIn("feature", types)
