from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User

from .models import Meetup


class PersonSerializer(serializers.ModelSerializer):
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "display_name", "initials"]


class MeetupSerializer(serializers.ModelSerializer):
    organizer = PersonSerializer(read_only=True)
    partner = PersonSerializer(read_only=True)
    gym_name = serializers.CharField(source="gym.name", read_only=True, default=None)
    mine = serializers.SerializerMethodField()

    class Meta:
        model = Meetup
        fields = ["id", "organizer", "partner", "gym", "gym_name", "starts_at", "focus", "status", "mine"]

    def get_mine(self, obj):
        """Vrai si l'utilisateur est celui qui doit répondre à l'invitation."""
        req = self.context.get("request")
        return bool(req and obj.partner_id == req.user.pk)


class MeetupCreateSerializer(serializers.Serializer):
    partner = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    starts_at = serializers.DateTimeField()
    gym = serializers.UUIDField(required=False, allow_null=True)
    focus = serializers.CharField(required=False, allow_blank=True, max_length=80)

    def validate_starts_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("L'heure de la séance doit être dans le futur.")
        return value

    def validate_partner(self, value):
        if value == self.context["request"].user:
            raise serializers.ValidationError("Tu ne peux pas organiser une séance avec toi-même.")
        return value
