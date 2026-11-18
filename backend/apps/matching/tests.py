from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member

from .services import compatibility


class CompatibilityTests(TestCase):
    def setUp(self):
        self.gym = make_gym()

    def test_identical_profiles_in_same_gym_score_100(self):
        a = make_member("Awa K.", gym=self.gym)
        b = make_member("Koffi Y.", gym=self.gym)
        score, reasons = compatibility(a.profile, b.profile)
        self.assertEqual(score, 100)
        self.assertTrue(reasons["gym"])

    def test_same_commune_without_overlap_scores_only_the_commune_bonus(self):
        a = make_member("Awa K.", gym=self.gym)
        other_gym = make_gym("Iron Temple", "Cocody")
        b = make_member("Koffi Y.", gym=other_gym, goals=["muscle"], level="avance", days=[1, 3], periods=["morning"])
        score, _ = compatibility(a.profile, b.profile)
        self.assertEqual(score, 10)

    def test_partial_overlap_is_proportional(self):
        a = make_member("Awa K.", gym=self.gym, days=[0, 2, 4])
        b = make_member("Koffi Y.", gym=self.gym, days=[0, 1])
        _, reasons = compatibility(a.profile, b.profile)
        self.assertEqual(reasons["days"], [0])
        score, _ = compatibility(a.profile, b.profile)
        # salle 35 + objectif 25 + jours 15 * (1/2) + créneaux 15 + niveau 10
        self.assertEqual(score, round(35 + 25 + 7.5 + 15 + 10))

    def test_commune_is_case_insensitive(self):
        a = make_member("Awa K.", commune="Cocody")
        b = make_member("Koffi Y.", commune="cocody")
        _, reasons = compatibility(a.profile, b.profile)
        self.assertTrue(reasons["commune"])


class MatchEndpointTests(APITestCase):
    def setUp(self):
        self.gym = make_gym()
        self.me = make_member("Olivier K.", gym=self.gym)

    def test_results_are_sorted_and_exclude_me(self):
        best = make_member("Awa K.", gym=self.gym)
        mid = make_member("Koffi Y.", gym=self.gym, goals=["muscle"])
        res = client_for(self.me).get("/api/matches/")
        self.assertEqual(res.status_code, 200)
        ids = [r["id"] for r in res.json()]
        self.assertEqual(ids, [str(best.id), str(mid.id)])
        self.assertNotIn(self.me.id, ids)

    def test_hidden_and_unfinished_profiles_are_not_listed(self):
        hidden = make_member("Caché", gym=self.gym, visible=False)
        unfinished = make_member("Pas fini", gym=self.gym, onboarded=False)
        ids = [r["id"] for r in client_for(self.me).get("/api/matches/").json()]
        self.assertNotIn(hidden.id, ids)
        self.assertNotIn(unfinished.id, ids)

    def test_other_communes_are_not_listed(self):
        far = make_member("Loin", commune="Yopougon", gym=make_gym("Autre", "Yopougon"))
        ids = [r["id"] for r in client_for(self.me).get("/api/matches/").json()]
        self.assertNotIn(far.id, ids)

    def test_minimum_score_filters_weak_matches(self):
        weak = make_member("Faible", gym=make_gym("Autre", "Cocody"), goals=["muscle"], level="avance", days=[6], periods=["morning"])
        ids = [r["id"] for r in client_for(self.me).get("/api/matches/").json()]
        self.assertNotIn(weak.id, ids)
        ids = [r["id"] for r in client_for(self.me).get("/api/matches/?min=0").json()]
        self.assertIn(str(weak.id), ids)

    def test_punctuality_is_hidden_when_the_member_opts_out(self):
        other = make_member("Awa K.", gym=self.gym, show_punctuality=False)
        row = next(r for r in client_for(self.me).get("/api/matches/").json() if r["id"] == str(other.id))
        self.assertIsNone(row["punctuality"])

    def test_requires_authentication(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get("/api/matches/").status_code, 401)

    def test_member_detail_includes_compatibility(self):
        other = make_member("Awa K.", gym=self.gym)
        res = client_for(self.me).get(f"/api/members/{other.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["score"], 100)
