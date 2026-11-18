import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from apps.accounts.testing import client_for, make_gym, make_member
from apps.chat.models import Message

from .models import Listing, Report

TMP_MEDIA = tempfile.mkdtemp(prefix="venolva-test-media-")


def png_bytes(size=(40, 30), mode="RGB", color=(200, 30, 30)):
    buf = BytesIO()
    Image.new(mode, size, color).save(buf, "PNG")
    return buf.getvalue()


def upload(data, name="photo.png", content_type="image/png"):
    return SimpleUploadedFile(name, data, content_type=content_type)


@override_settings(MEDIA_ROOT=TMP_MEDIA)
class ListingTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.gym = make_gym()
        self.seller = make_member("Koffi Y.", gym=self.gym)
        self.buyer = make_member("Olivier K.", gym=self.gym)

    def sell(self, user=None, **extra):
        body = {"title": "Haltères 2 × 10 kg", "price": 18000, "category": "weights", "condition": "very_good",
                "description": "Très bon état", "gym": self.gym.id}
        body.update(extra)
        return client_for(user or self.seller).post("/api/listings/", body, format="json")

    # --- création et règles ---
    def test_any_member_can_sell(self):
        res = self.sell()
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual((body["status"], body["mine"], body["seller"]["id"]), ("active", True, str(self.seller.id)))

    def test_validation(self):
        self.assertEqual(self.sell(price=100).status_code, 400)
        self.assertEqual(self.sell(price=6_000_000).status_code, 400)
        self.assertEqual(self.sell(title="ab").status_code, 400)
        self.assertEqual(self.sell(category="supplements").status_code, 400)  # catégories sensibles non proposées
        self.assertEqual(self.sell(status="sold").status_code, 400)

    def test_ten_active_listings_at_most(self):
        for i in range(10):
            self.assertEqual(self.sell(title=f"Article {i}").status_code, 201)
        self.assertEqual(self.sell(title="Onzième").status_code, 400)
        first = Listing.objects.filter(seller=self.seller).first()
        client_for(self.seller).patch(f"/api/listings/{first.id}/", {"status": "hidden"}, format="json")
        self.assertEqual(self.sell(title="Onzième").status_code, 201)

    def test_cannot_reactivate_beyond_the_limit(self):
        for i in range(10):
            self.sell(title=f"Article {i}")
        sold = Listing.objects.create(seller=self.seller, title="Vieux", price=1000, category="weights", status="sold")
        res = client_for(self.seller).patch(f"/api/listings/{sold.id}/", {"status": "active"}, format="json")
        self.assertEqual(res.status_code, 400)

    # --- lecture et filtres ---
    def test_listing_feed_only_shows_active_items_and_filters(self):
        a = self.sell(title="Haltères").json()["id"]
        b = self.sell(title="Tapis de yoga", category="accessories", price=6000).json()["id"]
        client_for(self.seller).patch(f"/api/listings/{b}/", {"status": "sold"}, format="json")
        feed = client_for(self.buyer).get("/api/listings/").json()["results"]
        self.assertEqual([x["id"] for x in feed], [a])
        self.assertEqual(len(client_for(self.buyer).get("/api/listings/?category=machines").json()["results"]), 0)
        self.assertEqual(len(client_for(self.buyer).get("/api/listings/?q=halt").json()["results"]), 1)
        self.assertEqual(len(client_for(self.buyer).get("/api/listings/?commune=Cocody").json()["results"]), 1)
        mine = client_for(self.seller).get("/api/listings/?mine=1").json()["results"]
        self.assertEqual({x["id"] for x in mine}, {a, b})

    def test_sold_listing_stays_visible_to_its_seller_only(self):
        lid = self.sell().json()["id"]
        client_for(self.seller).patch(f"/api/listings/{lid}/", {"status": "sold"}, format="json")
        self.assertEqual(client_for(self.seller).get(f"/api/listings/{lid}/").status_code, 200)
        self.assertEqual(client_for(self.buyer).get(f"/api/listings/{lid}/").status_code, 404)
        self.assertIsNotNone(Listing.objects.get(pk=lid).sold_at)

    # --- droits ---
    def test_only_the_seller_can_edit_or_delete(self):
        lid = self.sell().json()["id"]
        self.assertEqual(client_for(self.buyer).patch(f"/api/listings/{lid}/", {"price": 1000}, format="json").status_code, 403)
        self.assertEqual(client_for(self.buyer).delete(f"/api/listings/{lid}/").status_code, 403)
        self.assertEqual(client_for(self.seller).patch(f"/api/listings/{lid}/", {"price": 15000}, format="json").json()["price"], 15000)
        self.assertEqual(client_for(self.seller).delete(f"/api/listings/{lid}/").status_code, 204)

    def test_requires_authentication(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get("/api/listings/").status_code, 401)

    # --- contact et signalement ---
    def test_contact_opens_a_conversation_with_a_first_message(self):
        lid = self.sell().json()["id"]
        res = client_for(self.buyer).post(f"/api/listings/{lid}/contact/")
        self.assertEqual(res.status_code, 201)
        msg = Message.objects.get()
        self.assertEqual(msg.sender, self.buyer)
        self.assertIn("Haltères 2 × 10 kg", msg.body)
        # le vendeur voit la discussion avec un message non lu
        convs = client_for(self.seller).get("/api/conversations/").json()
        self.assertEqual(convs[0]["unread"], 1)

    def test_cannot_contact_oneself_or_a_sold_item(self):
        lid = self.sell().json()["id"]
        self.assertEqual(client_for(self.seller).post(f"/api/listings/{lid}/contact/").status_code, 400)
        client_for(self.seller).patch(f"/api/listings/{lid}/", {"status": "sold"}, format="json")
        self.assertEqual(client_for(self.buyer).post(f"/api/listings/{lid}/contact/").status_code, 404)

    def test_report_once_per_member_and_not_own_listing(self):
        lid = self.sell().json()["id"]
        url = f"/api/listings/{lid}/report/"
        self.assertEqual(client_for(self.buyer).post(url, {"reason": "scam", "detail": "Prix trop bas"}, format="json").status_code, 201)
        self.assertEqual(client_for(self.buyer).post(url, {"reason": "scam"}, format="json").status_code, 400)
        self.assertEqual(client_for(self.seller).post(url, {"reason": "scam"}, format="json").status_code, 400)
        self.assertEqual(client_for(self.buyer).post(url, {"reason": "inconnue"}, format="json").status_code, 400)
        self.assertEqual(Report.objects.count(), 1)

    # --- photos ---
    def add_photo(self, lid, data, user=None, **kw):
        return client_for(user or self.seller).post(f"/api/listings/{lid}/photos/", {"image": upload(data, **kw)}, format="multipart")

    def test_photo_is_reencoded_as_a_small_jpeg_without_metadata(self):
        lid = self.sell().json()["id"]
        res = self.add_photo(lid, png_bytes(size=(3000, 2000)))
        self.assertEqual(res.status_code, 201, res.content)
        photo = Listing.objects.get(pk=lid).photos.get()
        img = Image.open(photo.image.path)
        self.assertEqual(img.format, "JPEG")
        self.assertLessEqual(max(img.size), 1600)
        self.assertFalse(img.getexif())
        self.assertEqual(client_for(self.buyer).get(f"/api/listings/{lid}/").json()["photos"], [photo.image.url])

    def test_transparent_png_is_flattened(self):
        lid = self.sell().json()["id"]
        res = self.add_photo(lid, png_bytes(mode="RGBA", color=(0, 0, 0, 0)))
        self.assertEqual(res.status_code, 201, res.content)

    def test_non_images_are_refused(self):
        lid = self.sell().json()["id"]
        res = self.add_photo(lid, b"<?php echo 1; ?>", name="evil.jpg", content_type="image/jpeg")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Listing.objects.get(pk=lid).photos.count(), 0)

    def test_oversized_photo_is_refused(self):
        lid = self.sell().json()["id"]
        res = self.add_photo(lid, b"0" * (6 * 1024 * 1024 + 1))
        self.assertEqual(res.status_code, 400)

    def test_four_photos_at_most(self):
        lid = self.sell().json()["id"]
        for _ in range(4):
            self.assertEqual(self.add_photo(lid, png_bytes()).status_code, 201)
        self.assertEqual(self.add_photo(lid, png_bytes()).status_code, 400)

    def test_only_the_seller_adds_photos(self):
        lid = self.sell().json()["id"]
        self.assertEqual(self.add_photo(lid, png_bytes(), user=self.buyer).status_code, 404)

    def test_missing_file_is_refused(self):
        lid = self.sell().json()["id"]
        res = client_for(self.seller).post(f"/api/listings/{lid}/photos/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)
