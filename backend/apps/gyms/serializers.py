from django.utils import timezone
from rest_framework import serializers

from apps.backoffice.config import cfg

from .models import ClassBooking, Gym, GymClass, GymHours, GymPlan, GymReview, MembershipRequest


class GymSerializer(serializers.ModelSerializer):
    """Ligne de liste : salle avec nombre de membres et note."""

    members_count = serializers.IntegerField(read_only=True)
    rating_avg = serializers.FloatField(read_only=True, default=None)
    reviews_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Gym
        fields = ["id", "name", "commune", "address", "verified", "members_count", "rating_avg", "reviews_count"]


class HoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymHours
        fields = ["weekday", "opens", "closes"]

    def validate(self, attrs):
        if not 0 <= attrs["weekday"] <= 6:
            raise serializers.ValidationError("Jour invalide.")
        if attrs["closes"] <= attrs["opens"]:
            raise serializers.ValidationError("L'heure de fermeture doit suivre l'heure d'ouverture.")
        return attrs


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymPlan
        fields = ["id", "name", "description", "price", "active"]

    def validate_price(self, value):
        s = cfg()
        if not s.price_min_fcfa <= value <= s.price_max_fcfa:
            raise serializers.ValidationError(f"Le prix doit être entre {s.price_min_fcfa} et {s.price_max_fcfa} FCFA.")
        return value


class ClassSerializer(serializers.ModelSerializer):
    spots_left = serializers.SerializerMethodField()
    booked = serializers.SerializerMethodField()
    my_seat = serializers.SerializerMethodField()

    class Meta:
        model = GymClass
        fields = ["id", "name", "starts_at", "duration_min", "capacity", "price", "active", "spots_left", "booked", "my_seat"]
        read_only_fields = ["spots_left", "booked", "my_seat"]

    def get_spots_left(self, obj):
        count = getattr(obj, "booked_count", None)
        if count is None:
            count = obj.bookings.count()
        return max(0, obj.capacity - count)

    def get_booked(self, obj):
        req = self.context.get("request")
        return bool(req and ClassBooking.objects.filter(gym_class=obj, user=req.user).exists())

    def get_my_seat(self, obj):
        req = self.context.get("request")
        seat = ClassBooking.objects.filter(gym_class=obj, user=req.user).first() if req else None
        return {"id": seat.id, "paid": seat.paid} if seat else None

    def validate_starts_at(self, value):
        if self.instance is None and value <= timezone.now():
            raise serializers.ValidationError("Le cours doit être dans le futur.")
        return value

    def validate_capacity(self, value):
        if not 1 <= value <= 200:
            raise serializers.ValidationError("Entre 1 et 200 places.")
        return value

    def validate_duration_min(self, value):
        if not 15 <= value <= 240:
            raise serializers.ValidationError("La durée doit être entre 15 et 240 minutes.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = GymReview
        fields = ["id", "rating", "comment", "created_at", "author"]
        read_only_fields = ["id", "created_at", "author"]

    def get_author(self, obj):
        u = obj.user
        return {"id": u.id, "display_name": u.display_name, "initials": u.initials}

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("La note va de 1 à 5.")
        return value


class RequestSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    user = serializers.SerializerMethodField()
    gym_name = serializers.CharField(source="plan.gym.name", read_only=True)

    class Meta:
        model = MembershipRequest
        fields = ["id", "plan", "user", "gym_name", "status", "created_at"]

    def get_user(self, obj):
        u = obj.user
        return {"id": u.id, "display_name": u.display_name, "initials": u.initials, "commune": u.commune}
