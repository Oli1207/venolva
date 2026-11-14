from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.chat.models import Conversation

from .models import Availability, Booking, ProProfile, Service
from .services import free_slots, split_price


def day_ahead(days=7):
    return (timezone.localtime() + timedelta(days=days)).date()


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), timezone.get_current_timezone())


def make_pro(name="Coach Serge", pro_type="coach", verified=True, with_service=True, days_open=None, price=10000, kind="single"):
    """Un pro prêt à recevoir des réservations : disponible tous les jours de 8h à 12h."""
    user = make_member(name)
    user.pro_type, user.pro_verified = pro_type, verified
    user.save()
    ProProfile.objects.create(
        user=user, speciality="Préparation physique", credential="CERT-001",
        status="approved" if verified else "pending",
    )
    for wd in days_open if days_open is not None else range(7):
        Availability.objects.create(pro=user, weekday=wd, start=time(8), end=time(12))
    service = None
    if with_service:
        service = Service.objects.create(owner=user, name="Séance", kind=kind, price=price, duration_min=60, modes=["gym"])
    return user, service


class ApplyTests(APITestCase):
    def setUp(self):
        self.me = make_member("Fatou D.")

    def apply(self, **extra):
        body = {"pro_type": "nutrition", "speciality": "Perte de poids", "credential": "N° ordre 4521"}
        body.update(extra)
        return client_for(self.me).post("/api/pro/apply/", body, format="json")

    def test_application_is_pending_and_not_verified(self):
        res = self.apply()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "pending")
        self.me.refresh_from_db()
        self.assertEqual(self.me.pro_type, "nutrition")
        self.assertFalse(self.me.pro_verified)

    def test_credential_is_required(self):
        self.assertEqual(self.apply(credential="").status_code, 400)
        self.assertEqual(self.apply(pro_type="astronaute").status_code, 400)

    def test_pending_pro_cannot_create_services(self):
        self.apply()
        res = client_for(self.me).post(
            "/api/my/services/", {"name": "Consultation", "price": 15000, "modes": ["online"]}, format="json"
        )
        self.assertEqual(res.status_code, 403)

    def test_approval_unlocks_services_and_blocks_reapplying(self):
        self.apply()
        self.me.pro_profile.approve()
        res = client_for(self.me).post(
            "/api/my/services/", {"name": "Consultation", "price": 15000, "modes": ["online"], "duration_min": 45}, format="json"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.apply().status_code, 400)

    def test_rejection_removes_the_green_tick(self):
        self.apply()
        self.me.pro_profile.approve()
        self.me.pro_profile.reject("Diplôme illisible")
        self.me.refresh_from_db()
        self.assertFalse(self.me.pro_verified)
        state = client_for(self.me).get("/api/pro/me/").json()
        self.assertEqual((state["status"], state["review_note"]), ("rejected", "Diplôme illisible"))
        self.assertEqual(self.apply().status_code, 201)  # il peut renvoyer un dossier corrigé

    def test_state_before_applying_is_none(self):
        self.assertEqual(client_for(self.me).get("/api/pro/me/").json()["status"], "none")


class DirectoryTests(APITestCase):
    def setUp(self):
        self.viewer = make_member("Olivier K.")

    def test_only_validated_pros_with_services_are_listed(self):
        ok, _ = make_pro("Coach Serge")
        make_pro("Pas validé", verified=False)
        make_pro("Sans service", with_service=False)
        rows = client_for(self.viewer).get("/api/pros/").json()
        self.assertEqual([r["person"]["id"] for r in rows], [ok.id])
        self.assertEqual(rows[0]["min_price"], 10000)

    def test_type_filter(self):
        make_pro("Coach Serge")
        nutri, _ = make_pro("Fatou D.", pro_type="nutrition")
        rows = client_for(self.viewer).get("/api/pros/?type=nutrition").json()
        self.assertEqual([r["person"]["id"] for r in rows], [nutri.id])

    def test_detail_lists_only_active_services(self):
        pro, svc = make_pro()
        Service.objects.create(owner=pro, name="Caché", price=5000, modes=["gym"], active=False)
        res = client_for(self.viewer).get(f"/api/pros/{pro.id}/").json()
        self.assertEqual([s["id"] for s in res["services"]], [svc.id])
        self.assertEqual(res["weekdays"], [0, 1, 2, 3, 4, 5, 6])

    def test_unvalidated_pro_has_no_public_page(self):
        pro, _ = make_pro(verified=False)
        self.assertEqual(client_for(self.viewer).get(f"/api/pros/{pro.id}/").status_code, 404)


class ServiceTests(APITestCase):
    def setUp(self):
        self.pro, self.svc = make_pro()

    def create(self, **extra):
        body = {"name": "Bilan", "price": 8000, "modes": ["gym"], "duration_min": 30}
        body.update(extra)
        return client_for(self.pro).post("/api/my/services/", body, format="json")

    def test_validation(self):
        self.assertEqual(self.create(price=100).status_code, 400)
        self.assertEqual(self.create(modes=[]).status_code, 400)
        self.assertEqual(self.create(modes=["lune"]).status_code, 400)
        self.assertEqual(self.create(duration_min=7).status_code, 400)
        self.assertEqual(self.create().status_code, 201)

    def test_members_cannot_manage_services(self):
        member = make_member("Simple membre")
        self.assertEqual(client_for(member).get("/api/my/services/").status_code, 403)

    def test_cannot_edit_someone_elses_service(self):
        other, _ = make_pro("Autre coach")
        res = client_for(other).patch(f"/api/my/services/{self.svc.id}/", {"price": 1}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_deleting_a_booked_service_only_deactivates_it(self):
        client = make_member("Client")
        Booking.objects.create(
            service=self.svc, pro=self.pro, client=client, starts_at=at(day_ahead(), 9), ends_at=at(day_ahead(), 10),
            price_total=10000, price_client=10000,
        )
        self.assertEqual(client_for(self.pro).delete(f"/api/my/services/{self.svc.id}/").status_code, 204)
        self.svc.refresh_from_db()
        self.assertFalse(self.svc.active)

    def test_deleting_an_unused_service_removes_it(self):
        extra = Service.objects.create(owner=self.pro, name="Vide", price=3000, modes=["gym"])
        client_for(self.pro).delete(f"/api/my/services/{extra.id}/")
        self.assertFalse(Service.objects.filter(pk=extra.pk).exists())

    def test_availability_is_replaced_and_validated(self):
        c = client_for(self.pro)
        bad = c.put("/api/my/availability/", [{"weekday": 1, "start": "10:00", "end": "09:00"}], format="json")
        self.assertEqual(bad.status_code, 400)
        ok = c.put("/api/my/availability/", [{"weekday": 1, "start": "09:00", "end": "11:00"}], format="json")
        self.assertEqual(len(ok.json()), 1)
        self.assertEqual(Availability.objects.filter(pro=self.pro).count(), 1)


class SlotTests(APITestCase):
    def setUp(self):
        self.pro, self.svc = make_pro()
        self.day = day_ahead()

    def test_slots_follow_the_window_and_duration(self):
        starts = [timezone.localtime(s).strftime("%H:%M") for s in free_slots(self.pro, self.svc, self.day)]
        # fenêtre 8h-12h, séance d'1 h, pas de 30 min : dernier départ 11h
        self.assertEqual(starts, ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00"])

    def test_a_booking_removes_overlapping_slots(self):
        client = make_member("Client")
        Booking.objects.create(
            service=self.svc, pro=self.pro, client=client, starts_at=at(self.day, 9), ends_at=at(self.day, 10),
            price_total=10000, price_client=10000,
        )
        starts = [timezone.localtime(s).strftime("%H:%M") for s in free_slots(self.pro, self.svc, self.day)]
        self.assertEqual(starts, ["08:00", "10:00", "10:30", "11:00"])

    def test_cancelled_bookings_free_the_slot(self):
        client = make_member("Client")
        Booking.objects.create(
            service=self.svc, pro=self.pro, client=client, starts_at=at(self.day, 9), ends_at=at(self.day, 10),
            price_total=10000, price_client=10000, status="cancelled",
        )
        self.assertEqual(len(free_slots(self.pro, self.svc, self.day)), 7)

    def test_past_days_have_no_slots(self):
        self.assertEqual(free_slots(self.pro, self.svc, day_ahead(-2)), [])

    def test_closed_days_have_no_slots(self):
        closed_pro, svc = make_pro("Fermé", days_open=[])
        self.assertEqual(free_slots(closed_pro, svc, self.day), [])

    def test_endpoint(self):
        viewer = make_member("Olivier K.")
        res = client_for(viewer).get(f"/api/pros/{self.pro.id}/slots/?service={self.svc.id}&date={self.day.isoformat()}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 7)
        bad = client_for(viewer).get(f"/api/pros/{self.pro.id}/slots/?service={self.svc.id}&date=demain")
        self.assertEqual(bad.status_code, 400)


class PriceTests(APITestCase):
    def test_split(self):
        self.assertEqual(split_price(14000, True), (7000, 7000))
        self.assertEqual(split_price(14001, True), (7001, 7000))
        self.assertEqual(split_price(14000, False), (14000, 0))


class BookingTests(APITestCase):
    def setUp(self):
        self.pro, self.svc = make_pro()
        self.me = make_member("Olivier K.")
        self.day = day_ahead()

    def book(self, user=None, **extra):
        body = {"service": self.svc.id, "starts_at": at(self.day, 9).isoformat()}
        body.update(extra)
        return client_for(user or self.me).post("/api/bookings/", body, format="json")

    def test_booking_is_pending_and_opens_a_conversation(self):
        res = self.book()
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual((body["status"], body["payment_status"], body["role"]), ("pending", "unpaid", "client"))
        self.assertEqual(body["price_client"], 10000)
        self.assertTrue(Conversation.objects.exists())

    def test_cannot_book_outside_availability(self):
        self.assertEqual(self.book(starts_at=at(self.day, 14).isoformat()).status_code, 400)
        self.assertEqual(self.book(starts_at=at(self.day, 11, 30).isoformat()).status_code, 400)  # finirait à 12h30

    def test_cannot_double_book(self):
        self.assertEqual(self.book().status_code, 201)
        other = make_member("Awa K.")
        clash = self.book(user=other, starts_at=at(self.day, 9, 30).isoformat())
        self.assertEqual(clash.status_code, 400)

    def test_cannot_book_in_the_past_or_too_soon(self):
        self.assertEqual(self.book(starts_at=at(day_ahead(-1), 9).isoformat()).status_code, 400)
        soon = (timezone.now() + timedelta(minutes=20)).isoformat()
        self.assertEqual(self.book(starts_at=soon).status_code, 400)

    def test_cannot_book_own_service_or_inactive_or_unverified(self):
        self.assertEqual(self.book(user=self.pro).status_code, 400)
        self.svc.active = False
        self.svc.save()
        self.assertEqual(self.book().status_code, 400)
        self.svc.active = True
        self.svc.save()
        self.pro.pro_verified = False
        self.pro.save()
        self.assertEqual(self.book().status_code, 400)

    def test_mobile_payment_is_refused_for_now(self):
        res = self.book(payment_method="wave")
        self.assertEqual(res.status_code, 400)
        self.assertIn("payment_method", res.json())

    def test_unknown_place_is_refused(self):
        self.assertEqual(self.book(mode="home").status_code, 400)

    def test_duo_needs_a_partner_and_splits_the_price(self):
        duo = Service.objects.create(owner=self.pro, name="À deux", kind="duo", price=14000, duration_min=60, modes=["gym"])
        awa = make_member("Awa K.")
        self.assertEqual(self.book(service=duo.id).status_code, 400)
        res = self.book(service=duo.id, partner=awa.id)
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual((res.json()["price_total"], res.json()["price_client"]), (14000, 7000))
        # la partenaire voit la réservation
        listing = client_for(awa).get("/api/bookings/").json()
        self.assertEqual([b["role"] for b in listing], ["partner"])

    def test_individual_service_refuses_a_partner(self):
        awa = make_member("Awa K.")
        self.assertEqual(self.book(partner=awa.id).status_code, 400)

    def test_partner_cannot_be_oneself_or_the_pro(self):
        duo = Service.objects.create(owner=self.pro, name="À deux", kind="duo", price=14000, modes=["gym"])
        self.assertEqual(self.book(service=duo.id, partner=self.me.id).status_code, 400)
        self.assertEqual(self.book(service=duo.id, partner=self.pro.id).status_code, 400)


class BookingActionTests(APITestCase):
    def setUp(self):
        self.pro, self.svc = make_pro()
        self.me = make_member("Olivier K.")
        self.day = day_ahead()
        self.b = Booking.objects.create(
            service=self.svc, pro=self.pro, client=self.me, starts_at=at(self.day, 9), ends_at=at(self.day, 10),
            price_total=10000, price_client=10000,
        )

    def act(self, user, action):
        return client_for(user).post(f"/api/bookings/{self.b.id}/{action}/")

    def test_only_the_pro_can_confirm_or_decline(self):
        self.assertEqual(self.act(self.me, "confirm").status_code, 400)
        res = self.act(self.pro, "confirm")
        self.assertEqual(res.json()["status"], "confirmed")
        self.assertEqual(self.act(self.pro, "decline").status_code, 400)  # déjà répondu

    def test_decline(self):
        self.assertEqual(self.act(self.pro, "decline").json()["status"], "declined")

    def test_client_can_cancel_and_it_frees_the_slot(self):
        self.assertEqual(self.act(self.me, "cancel").json()["status"], "cancelled")
        self.assertEqual(self.act(self.me, "cancel").status_code, 400)
        self.assertEqual(len(free_slots(self.pro, self.svc, self.day)), 7)

    def test_strangers_get_404(self):
        stranger = make_member("Intrus")
        self.assertEqual(self.act(stranger, "cancel").status_code, 404)
        self.assertEqual(self.act(self.me, "inconnue").status_code, 404)

    def test_complete_needs_a_confirmed_booking_whose_time_has_passed(self):
        self.act(self.pro, "confirm")
        self.assertEqual(self.act(self.pro, "complete").status_code, 400)  # dans le futur
        self.b.refresh_from_db()
        self.b.starts_at, self.b.ends_at = timezone.now() - timedelta(hours=2), timezone.now() - timedelta(hours=1)
        self.b.save()
        self.assertEqual(self.act(self.me, "complete").status_code, 400)
        self.assertEqual(self.act(self.pro, "complete").json()["status"], "done")

    def test_mark_paid_is_for_the_pro_only(self):
        self.assertEqual(self.act(self.me, "mark_paid").status_code, 400)
        self.assertEqual(self.act(self.pro, "mark_paid").json()["payment_status"], "paid")

    def test_cannot_mark_a_cancelled_booking_as_paid(self):
        self.act(self.me, "cancel")
        self.assertEqual(self.act(self.pro, "mark_paid").status_code, 400)

    def test_listing_by_role(self):
        self.assertEqual(len(client_for(self.pro).get("/api/bookings/?role=pro").json()), 1)
        self.assertEqual(len(client_for(self.pro).get("/api/bookings/").json()), 0)
        self.assertEqual(len(client_for(self.me).get("/api/bookings/").json()), 1)

    def test_pros_get_their_done_count_in_the_directory(self):
        self.b.status = "done"
        self.b.save()
        row = client_for(self.me).get("/api/pros/").json()[0]
        self.assertEqual(row["sessions_done"], 1)
