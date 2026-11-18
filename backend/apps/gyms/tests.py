from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.chat.models import Message

from .models import ClassBooking, Gym, GymClass, GymHours, GymPlan, GymReview, MembershipRequest


def make_manager(name="Gérant", verified=True):
    user = make_member(name)
    user.pro_type, user.pro_verified = "gym", verified
    user.save()
    return user


def make_owned_gym(name="Salle Riviera 3", owner=None, commune="Cocody"):
    owner = owner or make_manager()
    return Gym.objects.create(name=name, commune=commune, owner=owner, verified=True), owner


def future(hours=48):
    return (timezone.now() + timedelta(hours=hours)).isoformat()


def monday_at(hour, minute=0):
    return timezone.make_aware(datetime(2026, 11, 16, hour, minute), timezone.get_current_timezone())  # un lundi


class PublicProfileTests(APITestCase):
    def setUp(self):
        self.gym, self.owner = make_owned_gym()
        self.me = make_member("Olivier K.", gym=self.gym)
        self.plan = GymPlan.objects.create(gym=self.gym, name="Mensuel", price=25000)
        GymPlan.objects.create(gym=self.gym, name="Caché", price=1000, active=False)

    def test_detail_has_the_whole_profile(self):
        GymHours.objects.create(gym=self.gym, weekday=0, opens=time(5), closes=time(22))
        res = client_for(self.me).get(f"/api/gyms/{self.gym.id}/").json()
        self.assertEqual(res["name"], "Salle Riviera 3")
        self.assertEqual(res["members_count"], 1)
        self.assertEqual([p["name"] for p in res["plans"]], ["Mensuel"])  # les formules inactives sont cachées
        self.assertEqual(res["hours"][0]["weekday"], 0)
        self.assertIsNone(res["rating_avg"])
        self.assertFalse(res["is_owner"])
        self.assertTrue(client_for(self.owner).get(f"/api/gyms/{self.gym.id}/").json()["is_owner"])

    def test_open_now_follows_the_hours_of_the_day(self):
        GymHours.objects.create(gym=self.gym, weekday=0, opens=time(5), closes=time(22))
        with patch("apps.gyms.models.timezone.localtime", return_value=monday_at(10)):
            self.assertTrue(self.gym.is_open_now())
            self.assertEqual(client_for(self.me).get(f"/api/gyms/{self.gym.id}/").json()["today"], {"opens": "05:00", "closes": "22:00"})
        with patch("apps.gyms.models.timezone.localtime", return_value=monday_at(23)):
            self.assertFalse(self.gym.is_open_now())
        with patch("apps.gyms.models.timezone.localtime", return_value=monday_at(4, 30)):
            self.assertFalse(self.gym.is_open_now())
        with patch("apps.gyms.models.timezone.localtime", return_value=monday_at(10) + timedelta(days=1)):  # mardi : fermé
            self.assertFalse(self.gym.is_open_now())
            self.assertIsNone(client_for(self.me).get(f"/api/gyms/{self.gym.id}/").json()["today"])

    def test_list_carries_rating_and_member_count(self):
        GymReview.objects.create(gym=self.gym, user=self.me, rating=4)
        GymReview.objects.create(gym=self.gym, user=make_member("Awa K."), rating=5)
        row = next(g for g in client_for(self.me).get("/api/gyms/").json() if g["id"] == str(self.gym.id))
        self.assertEqual((row["rating_avg"], row["reviews_count"], row["members_count"]), (4.5, 2, 1))

    def test_unknown_gym_is_404(self):
        self.assertEqual(client_for(self.me).get("/api/gyms/00000000-0000-0000-0000-000000000001/").status_code, 404)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get(f"/api/gyms/{self.gym.id}/").status_code, 401)


class ReviewTests(APITestCase):
    def setUp(self):
        self.gym, self.owner = make_owned_gym()
        self.me = make_member("Olivier K.")

    def review(self, user=None, **body):
        return client_for(user or self.me).post(f"/api/gyms/{self.gym.id}/reviews/", body, format="json")

    def test_one_review_per_member_and_it_can_be_edited(self):
        self.assertEqual(self.review(rating=3, comment="Correct").status_code, 201)
        self.assertEqual(self.review(rating=5, comment="Très bien").status_code, 201)
        self.assertEqual(GymReview.objects.count(), 1)
        detail = client_for(self.me).get(f"/api/gyms/{self.gym.id}/").json()
        self.assertEqual((detail["rating_avg"], detail["my_review"]["rating"]), (5.0, 5))

    def test_rating_must_be_between_1_and_5(self):
        for bad in (0, 6, -1):
            self.assertEqual(self.review(rating=bad).status_code, 400)

    def test_owner_cannot_rate_own_gym(self):
        self.assertEqual(self.review(user=self.owner, rating=5).status_code, 400)

    def test_listing_reviews(self):
        self.review(rating=4, comment="Bien")
        rows = client_for(self.me).get(f"/api/gyms/{self.gym.id}/reviews/").json()
        self.assertEqual([(r["rating"], r["comment"], r["author"]["display_name"]) for r in rows], [(4, "Bien", "Olivier K.")])


class MembershipRequestTests(APITestCase):
    def setUp(self):
        self.gym, self.owner = make_owned_gym()
        self.plan = GymPlan.objects.create(gym=self.gym, name="Mensuel", price=25000)
        self.me = make_member("Olivier K.")

    def ask(self, user=None, plan=None):
        return client_for(user or self.me).post(f"/api/gym-plans/{(plan or self.plan).id}/request/")

    def test_request_notifies_the_gym_by_message(self):
        res = self.ask()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "pending")
        msg = Message.objects.get()
        self.assertEqual(msg.sender, self.me)
        self.assertIn("Mensuel", msg.body)
        self.assertIn("25 000 F", msg.body)

    def test_no_duplicate_pending_request_and_no_self_request(self):
        self.ask()
        self.assertEqual(self.ask().status_code, 400)
        self.assertEqual(self.ask(user=self.owner).status_code, 400)

    def test_inactive_plan_is_not_requestable(self):
        self.plan.active = False
        self.plan.save()
        self.assertEqual(self.ask().status_code, 404)

    def test_member_can_cancel_a_pending_request_once(self):
        rid = self.ask().json()["id"]
        self.assertEqual(client_for(self.me).post(f"/api/gym-requests/{rid}/cancel/").json()["status"], "cancelled")
        self.assertEqual(client_for(self.me).post(f"/api/gym-requests/{rid}/cancel/").status_code, 400)
        self.assertEqual(self.ask().status_code, 201)  # il peut redemander ensuite

    def test_my_requests_only_lists_mine(self):
        self.ask()
        self.ask(user=make_member("Awa K."))
        self.assertEqual(len(client_for(self.me).get("/api/gym-requests/").json()), 1)

    def test_gym_without_owner_still_records_the_request(self):
        orphan = make_gym("Sans gérant")
        plan = GymPlan.objects.create(gym=orphan, name="Séance", price=2000)
        self.assertEqual(self.ask(plan=plan).status_code, 201)
        self.assertEqual(Message.objects.count(), 0)


class ClassBookingTests(APITestCase):
    def setUp(self):
        self.gym, self.owner = make_owned_gym()
        self.cls = GymClass.objects.create(gym=self.gym, name="Zumba", starts_at=timezone.now() + timedelta(days=2), capacity=2)
        self.a, self.b, self.c = make_member("A"), make_member("B"), make_member("C")

    def act(self, user, action="book", cls=None):
        return client_for(user).post(f"/api/gym-classes/{(cls or self.cls).id}/{action}/")

    def test_booking_and_spots_left(self):
        res = self.act(self.a)
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.json()["spots_left"], res.json()["booked"]), (1, True))
        detail = client_for(self.b).get(f"/api/gyms/{self.gym.id}/").json()["classes"][0]
        self.assertEqual((detail["spots_left"], detail["booked"]), (1, False))

    def test_full_class_refuses_new_bookings(self):
        self.act(self.a)
        self.act(self.b)
        res = self.act(self.c)
        self.assertEqual(res.status_code, 400)
        self.assertIn("complet", res.json()["detail"])

    def test_cannot_book_twice(self):
        self.act(self.a)
        self.assertEqual(self.act(self.a).status_code, 400)
        self.assertEqual(ClassBooking.objects.count(), 1)

    def test_cancelling_frees_the_seat(self):
        self.act(self.a)
        self.act(self.b)
        self.assertEqual(self.act(self.a, "cancel").status_code, 200)
        self.assertEqual(self.act(self.c).status_code, 200)
        self.assertEqual(self.act(self.a, "cancel").status_code, 400)  # plus de place à annuler

    def test_started_or_inactive_classes_are_closed(self):
        past = GymClass.objects.create(gym=self.gym, name="Passé", starts_at=timezone.now() - timedelta(hours=1), capacity=5)
        self.assertEqual(self.act(self.a, cls=past).status_code, 400)
        self.cls.active = False
        self.cls.save()
        self.assertEqual(self.act(self.a).status_code, 404)

    def test_unknown_action(self):
        self.assertEqual(self.act(self.a, "supprimer").status_code, 404)


class ManagerAccessTests(APITestCase):
    def test_plain_members_and_unverified_gyms_are_refused(self):
        member = make_member("Simple")
        self.assertEqual(client_for(member).get("/api/my/gym/").status_code, 403)
        pending = make_manager("En attente", verified=False)
        self.assertEqual(client_for(pending).post("/api/my/gym/", {"name": "X", "commune": "Cocody"}, format="json").status_code, 403)

    def test_a_verified_gym_pro_creates_one_gym(self):
        boss = make_manager()
        c = client_for(boss)
        self.assertEqual(c.get("/api/my/gym/").status_code, 404)
        res = c.post("/api/my/gym/", {"name": "Yop Fitness", "commune": "Yopougon", "equipment": ["Cardio"]}, format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertTrue(res.json()["verified"])
        self.assertTrue(res.json()["is_owner"])
        self.assertEqual(c.post("/api/my/gym/", {"name": "Autre", "commune": "Cocody"}, format="json").status_code, 400)

    def test_name_and_commune_are_required(self):
        res = client_for(make_manager()).post("/api/my/gym/", {"name": " "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_an_owner_assigned_in_the_back_office_gets_access(self):
        gym = make_gym("Salle existante")
        member = make_member("Futur gérant")
        gym.owner = member
        gym.save()
        self.assertEqual(client_for(member).get("/api/my/gym/").status_code, 200)

    def test_patch_validates_and_saves(self):
        gym, boss = make_owned_gym()
        c = client_for(boss)
        ok = c.patch("/api/my/gym/", {"description": "La salle du quartier", "equipment": ["Musculation", "Douches"]}, format="json")
        self.assertEqual(ok.status_code, 200)
        gym.refresh_from_db()
        self.assertEqual(gym.equipment, ["Musculation", "Douches"])
        self.assertEqual(c.patch("/api/my/gym/", {"equipment": ["x"] * 13}, format="json").status_code, 400)
        self.assertEqual(c.patch("/api/my/gym/", {"equipment": "Cardio"}, format="json").status_code, 400)
        self.assertEqual(c.patch("/api/my/gym/", {"name": "x" * 121}, format="json").status_code, 400)

    def test_cannot_change_the_owner_through_the_api(self):
        gym, boss = make_owned_gym()
        other = make_member("Autre")
        client_for(boss).patch("/api/my/gym/", {"owner": other.id, "verified": False}, format="json")
        gym.refresh_from_db()
        self.assertEqual(gym.owner, boss)
        self.assertTrue(gym.verified)


class ManagerHoursPlansTests(APITestCase):
    def setUp(self):
        self.gym, self.boss = make_owned_gym()
        self.c = client_for(self.boss)

    def test_hours_are_replaced_and_validated(self):
        ok = self.c.put("/api/my/gym/hours/", [{"weekday": 0, "opens": "05:00", "closes": "22:00"}, {"weekday": 6, "opens": "08:00", "closes": "20:00"}], format="json")
        self.assertEqual(len(ok.json()), 2)
        again = self.c.put("/api/my/gym/hours/", [{"weekday": 2, "opens": "06:00", "closes": "21:00"}], format="json")
        self.assertEqual([h["weekday"] for h in again.json()], [2])
        self.assertEqual(self.gym.hours.count(), 1)

    def test_bad_hours_are_refused(self):
        self.assertEqual(self.c.put("/api/my/gym/hours/", [{"weekday": 0, "opens": "10:00", "closes": "09:00"}], format="json").status_code, 400)
        self.assertEqual(self.c.put("/api/my/gym/hours/", [{"weekday": 9, "opens": "08:00", "closes": "09:00"}], format="json").status_code, 400)
        twice = [{"weekday": 1, "opens": "08:00", "closes": "09:00"}, {"weekday": 1, "opens": "10:00", "closes": "11:00"}]
        self.assertEqual(self.c.put("/api/my/gym/hours/", twice, format="json").status_code, 400)

    def test_plan_crud(self):
        res = self.c.post("/api/my/gym/plans/", {"name": "Trimestriel", "description": "3 mois", "price": 65000}, format="json")
        self.assertEqual(res.status_code, 201)
        pid = res.json()["id"]
        self.assertEqual(self.c.post("/api/my/gym/plans/", {"name": "Gratuit", "price": 0}, format="json").status_code, 400)
        self.assertEqual(self.c.patch(f"/api/my/gym/plans/{pid}/", {"price": 60000}, format="json").json()["price"], 60000)
        self.assertEqual(self.c.delete(f"/api/my/gym/plans/{pid}/").status_code, 204)
        self.assertFalse(GymPlan.objects.filter(pk=pid).exists())

    def test_deleting_a_requested_plan_only_deactivates_it(self):
        plan = GymPlan.objects.create(gym=self.gym, name="Mensuel", price=25000)
        MembershipRequest.objects.create(plan=plan, user=make_member("Olivier K."))
        self.c.delete(f"/api/my/gym/plans/{plan.id}/")
        plan.refresh_from_db()
        self.assertFalse(plan.active)

    def test_another_gym_owner_cannot_touch_my_plans(self):
        plan = GymPlan.objects.create(gym=self.gym, name="Mensuel", price=25000)
        _, rival = make_owned_gym("Concurrent", make_manager("Rival"))
        self.assertEqual(client_for(rival).patch(f"/api/my/gym/plans/{plan.id}/", {"price": 1}, format="json").status_code, 404)
        self.assertEqual(client_for(rival).delete(f"/api/my/gym/plans/{plan.id}/").status_code, 404)


class ManagerClassesAndRequestsTests(APITestCase):
    def setUp(self):
        self.gym, self.boss = make_owned_gym()
        self.c = client_for(self.boss)

    def make_class(self, **extra):
        body = {"name": "Zumba", "starts_at": future(), "capacity": 10, "duration_min": 60, "price": 2000}
        body.update(extra)
        return self.c.post("/api/my/gym/classes/", body, format="json")

    def test_class_validation(self):
        self.assertEqual(self.make_class().status_code, 201)
        self.assertEqual(self.make_class(starts_at=future(-5)).status_code, 400)
        self.assertEqual(self.make_class(capacity=0).status_code, 400)
        self.assertEqual(self.make_class(capacity=500).status_code, 400)
        self.assertEqual(self.make_class(duration_min=5).status_code, 400)

    def test_capacity_cannot_drop_below_bookings(self):
        cid = self.make_class(capacity=3).json()["id"]
        for n in ("A", "B"):
            ClassBooking.objects.create(gym_class_id=cid, user=make_member(n))
        self.assertEqual(self.c.patch(f"/api/my/gym/classes/{cid}/", {"capacity": 1}, format="json").status_code, 400)
        self.assertEqual(self.c.patch(f"/api/my/gym/classes/{cid}/", {"capacity": 2}, format="json").status_code, 200)

    def test_deleted_class_disappears_from_the_public_profile(self):
        cid = self.make_class().json()["id"]
        viewer = make_member("Olivier K.")
        self.assertEqual(len(client_for(viewer).get(f"/api/gyms/{self.gym.id}/").json()["classes"]), 1)
        self.c.delete(f"/api/my/gym/classes/{cid}/")
        self.assertEqual(len(client_for(viewer).get(f"/api/gyms/{self.gym.id}/").json()["classes"]), 0)
        self.assertTrue(GymClass.objects.filter(pk=cid).exists())  # la trace reste

    def test_participants_are_visible_to_the_owner_only(self):
        cid = self.make_class().json()["id"]
        ClassBooking.objects.create(gym_class_id=cid, user=make_member("Awa K."))
        rows = self.c.get(f"/api/my/gym/classes/{cid}/participants/").json()
        self.assertEqual([r["display_name"] for r in rows], ["Awa K."])
        _, rival = make_owned_gym("Concurrent", make_manager("Rival"))
        self.assertEqual(client_for(rival).get(f"/api/my/gym/classes/{cid}/participants/").status_code, 404)

    def test_owner_answers_membership_requests(self):
        plan = GymPlan.objects.create(gym=self.gym, name="Mensuel", price=25000)
        member = make_member("Olivier K.")
        rid = client_for(member).post(f"/api/gym-plans/{plan.id}/request/").json()["id"]
        pending = self.c.get("/api/my/gym/requests/?status=pending").json()
        self.assertEqual([r["user"]["display_name"] for r in pending], ["Olivier K."])
        self.assertEqual(self.c.post(f"/api/my/gym/requests/{rid}/accept/").json()["status"], "accepted")
        self.assertEqual(self.c.post(f"/api/my/gym/requests/{rid}/decline/").status_code, 400)  # déjà répondu
        self.assertEqual(self.c.get("/api/my/gym/requests/?status=pending").json(), [])

    def test_other_gyms_requests_are_invisible(self):
        plan = GymPlan.objects.create(gym=self.gym, name="Mensuel", price=25000)
        rid = client_for(make_member("Olivier K.")).post(f"/api/gym-plans/{plan.id}/request/").json()["id"]
        _, rival = make_owned_gym("Concurrent", make_manager("Rival"))
        self.assertEqual(client_for(rival).get("/api/my/gym/requests/").json(), [])
        self.assertEqual(client_for(rival).post(f"/api/my/gym/requests/{rid}/accept/").status_code, 404)

    def test_unknown_request_action(self):
        self.assertEqual(self.c.post("/api/my/gym/requests/00000000-0000-0000-0000-000000000001/explode/").status_code, 404)
