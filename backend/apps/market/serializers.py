from rest_framework import serializers

from apps.backoffice.config import cfg

from .models import Listing, Report


class ListingSerializer(serializers.ModelSerializer):
    seller = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    gym_name = serializers.CharField(source="gym.name", read_only=True, default=None)
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "category", "condition", "gym", "gym_name", "handover_at_gym",
            "status", "created_at", "seller", "photos", "mine",
        ]
        read_only_fields = ["id", "created_at", "seller", "photos", "mine", "gym_name"]

    def get_seller(self, obj):
        s = obj.seller
        return {"id": s.id, "display_name": s.display_name, "initials": s.initials, "commune": s.commune,
                "pro_type": s.pro_type, "pro_verified": s.pro_verified}

    def get_photos(self, obj):
        return [p.image.url for p in obj.photos.all()]

    def get_mine(self, obj):
        return obj.seller_id == self.context["request"].user.pk

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Le titre doit faire au moins 3 caractères.")
        return value

    def validate_price(self, value):
        s = cfg()
        if not s.price_min_fcfa <= value <= s.price_max_fcfa:
            raise serializers.ValidationError(f"Le prix doit être entre {s.price_min_fcfa} et {s.price_max_fcfa} FCFA.")
        return value

    def validate_status(self, value):
        # Le vendeur peut vendre, retirer ou remettre en vente, rien d'autre.
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        creating = self.instance is None
        becoming_active = attrs.get("status", Listing.Status.ACTIVE) == Listing.Status.ACTIVE and (
            creating or self.instance.status != Listing.Status.ACTIVE
        )
        if becoming_active:
            active = Listing.objects.filter(seller=user, status=Listing.Status.ACTIVE).count()
            limit = cfg().max_active_listings
            if active >= limit:
                raise serializers.ValidationError(
                    f"Tu as déjà {limit} annonces en vente. Retire-en une pour en publier une autre."
                )
        if creating and attrs.get("status") not in (None, Listing.Status.ACTIVE):
            raise serializers.ValidationError({"status": "Une nouvelle annonce est en vente."})
        return attrs


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["reason", "detail"]
