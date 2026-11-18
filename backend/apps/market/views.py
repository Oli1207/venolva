from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Message
from apps.chat.services import get_or_create_conversation
from apps.promo.services import featured_ids
from apps.safety.services import blocked_ids

from apps.backoffice.config import cfg

from .images import clean_image
from .models import Listing, ListingPhoto
from .serializers import ListingSerializer, ReportSerializer



class IsSellerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.method in ("GET", "HEAD", "OPTIONS") or obj.seller_id == request.user.pk


def visible_to(user):
    """Les annonces en vente pour tout le monde, plus toutes les miennes."""
    return Listing.objects.filter(Q(status=Listing.Status.ACTIVE) | Q(seller=user)).select_related("seller", "gym").prefetch_related("photos")


class ListingListCreateView(ListCreateAPIView):
    """GET /api/listings/?category=weights&q=haltères&commune=Cocody&mine=1 puis POST pour vendre."""

    serializer_class = ListingSerializer

    def get_queryset(self):
        u = self.request.user
        p = self.request.query_params
        if p.get("mine") == "1":
            qs = Listing.objects.filter(seller=u).select_related("seller", "gym").prefetch_related("photos")
        else:
            qs = Listing.objects.filter(status=Listing.Status.ACTIVE).select_related("seller", "gym").prefetch_related("photos")
        if p.get("mine") != "1":
            top = featured_ids("listing", u.commune or "")
            qs = qs.annotate(_top=Case(When(pk__in=top, then=0), default=1, output_field=IntegerField())).order_by("_top", "-created_at")
        if p.get("category") in dict(Listing.Category.choices):
            qs = qs.filter(category=p["category"])
        if p.get("q"):
            qs = qs.filter(Q(title__icontains=p["q"]) | Q(description__icontains=p["q"]))
        if p.get("commune"):
            qs = qs.filter(Q(seller__commune__iexact=p["commune"]) | Q(gym__commune__iexact=p["commune"]))
        return qs

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class ListingDetailView(RetrieveUpdateDestroyAPIView):
    serializer_class = ListingSerializer
    permission_classes = [IsSellerOrReadOnly]

    def get_queryset(self):
        return visible_to(self.request.user)

    def perform_update(self, serializer):
        new_status = serializer.validated_data.get("status")
        extra = {}
        if new_status == Listing.Status.SOLD:
            extra["sold_at"] = timezone.now()
        serializer.save(**extra)


class ListingPhotoView(APIView):
    """POST /api/listings/<id>/photos/ (multipart, champ « image ») : ajoute une photo, 4 au maximum."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, seller=request.user)
        upload = request.FILES.get("image")
        if upload is None:
            return Response({"image": ["Ajoute une photo."]}, status=status.HTTP_400_BAD_REQUEST)
        max_photos = cfg().max_listing_photos
        if listing.photos.count() >= max_photos:
            return Response({"detail": f"{max_photos} photos au maximum."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cleaned = clean_image(upload)
        except ValidationError as exc:
            return Response({"image": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        photo = ListingPhoto.objects.create(listing=listing, position=listing.photos.count())
        photo.image.save("photo.jpg", cleaned, save=True)
        return Response({"url": photo.image.url}, status=status.HTTP_201_CREATED)


class ListingContactView(APIView):
    """POST /api/listings/<id>/contact/ : ouvre la discussion avec le vendeur et envoie un premier message."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, status=Listing.Status.ACTIVE)
        if listing.seller_id == request.user.pk:
            return Response({"detail": "C'est ton annonce."}, status=status.HTTP_400_BAD_REQUEST)
        if listing.seller_id in blocked_ids(request.user):
            return Response({"detail": "Tu ne peux pas contacter ce vendeur."}, status=status.HTTP_400_BAD_REQUEST)
        conv = get_or_create_conversation(request.user, listing.seller)
        price = f"{listing.price:,}".replace(",", " ")
        body = f"Bonjour, ton annonce « {listing.title} » ({price} F) est-elle toujours disponible ?"
        Message.objects.create(conversation=conv, sender=request.user, body=body[:1000])
        conv.save(update_fields=["updated_at"])
        return Response({"conversation": conv.id}, status=status.HTTP_201_CREATED)


class ListingReportView(APIView):
    """POST /api/listings/<id>/report/ {reason, detail}."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk)
        if listing.seller_id == request.user.pk:
            return Response({"detail": "Tu ne peux pas signaler ta propre annonce."}, status=status.HTTP_400_BAD_REQUEST)
        ser = ReportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            with transaction.atomic():  # isole l'erreur pour ne pas casser une transaction englobante
                ser.save(listing=listing, reporter=request.user)
        except IntegrityError:
            return Response({"detail": "Tu as déjà signalé cette annonce."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Merci, l'équipe va examiner cette annonce."}, status=status.HTTP_201_CREATED)
