from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User

from apps.backoffice.config import cfg

from . import services as slots
from .models import Availability, Booking, ProProfile, Service


class PersonSerializer(serializers.ModelSerializer):
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "display_name", "initials", "commune", "pro_type", "pro_verified"]


class ProApplySerializer(serializers.Serializer):
    pro_type = serializers.ChoiceField(choices=User.ProType.choices)
    speciality = serializers.CharField(max_length=80, allow_blank=True, required=False)
    bio = serializers.CharField(max_length=300, allow_blank=True, required=False)
    credential = serializers.CharField(min_length=3, max_length=160)
    gym = serializers.UUIDField(required=False, allow_null=True)
    years_experience = serializers.IntegerField(min_value=0, max_value=60, required=False, allow_null=True)


class ServiceSerializer(serializers.ModelSerializer):
    gym_name = serializers.CharField(source="gym.name", read_only=True, default=None)

    class Meta:
        model = Service
        fields = [
            "id", "name", "kind", "duration_min", "price", "modes", "gym", "gym_name", "description", "active",
        ]

    def validate_modes(self, value):
        if not value or any(m not in Service.MODES for m in value):
            raise serializers.ValidationError("Choisis au moins un lieu : salle, domicile ou en ligne.")
        return sorted(set(value))

    def validate_price(self, value):
        s = cfg()
        if not s.price_min_fcfa <= value <= s.price_max_fcfa:
            raise serializers.ValidationError(f"Le prix doit être entre {s.price_min_fcfa} et {s.price_max_fcfa} FCFA.")
        return value

    def validate_duration_min(self, value):
        if not 15 <= value <= 240 or value % 5:
            raise serializers.ValidationError("La durée doit être entre 15 et 240 minutes, par pas de 5.")
        return value


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = ["weekday", "start", "end"]

    def validate(self, attrs):
        if not 0 <= attrs["weekday"] <= 6:
            raise serializers.ValidationError("Jour invalide.")
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError("L'heure de fin doit suivre l'heure de début.")
        return attrs


class BookingSerializer(serializers.ModelSerializer):
    service = ServiceSerializer(read_only=True)
    pro = PersonSerializer(read_only=True)
    client = PersonSerializer(read_only=True)
    partner = PersonSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    gym_name = serializers.SerializerMethodField()
    my_share = serializers.SerializerMethodField()
    paid_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "service", "pro", "client", "partner", "role", "starts_at", "ends_at", "mode", "status",
            "payment_status", "payment_method", "price_total", "price_client", "note", "gym_name", "my_share", "paid_by_me",
        ]

    def get_my_share(self, obj):
        """Ce que le visiteur doit payer : sa part, ou rien pour le pro."""
        uid = self.context["request"].user.pk
        if uid == obj.client_id:
            return obj.price_client
        return obj.price_total - obj.price_client if uid == obj.partner_id else None

    def get_paid_by_me(self, obj):
        from apps.payments.models import Payment  # import tardif : payments dépend de pros

        uid = self.context["request"].user.pk
        return Payment.objects.filter(user_id=uid, purpose="booking", target_id=obj.pk, status="paid").exists()

    def get_role(self, obj):
        uid = self.context["request"].user.pk
        return "pro" if obj.pro_id == uid else "partner" if obj.partner_id == uid else "client"

    def get_gym_name(self, obj):
        return obj.service.gym.name if obj.service.gym_id else None


class BookingCreateSerializer(serializers.Serializer):
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(active=True, owner__pro_verified=True))
    starts_at = serializers.DateTimeField()
    mode = serializers.ChoiceField(choices=Service.MODES, required=False)
    partner = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=Booking.Method.choices, default=Booking.Method.CASH)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        client = self.context["request"].user
        service, start = attrs["service"], attrs["starts_at"]
        pro = service.owner
        partner = attrs.get("partner")

        if pro == client:
            raise serializers.ValidationError({"service": "Tu ne peux pas réserver tes propres services."})
        mode = attrs.get("mode") or service.modes[0]
        if mode not in service.modes:
            raise serializers.ValidationError({"mode": "Ce lieu n'est pas proposé pour ce service."})
        if service.is_duo and not partner:
            raise serializers.ValidationError({"partner": "Une séance à deux demande un binôme."})
        if partner and not service.is_duo:
            raise serializers.ValidationError({"partner": "Ce service est individuel."})
        if partner and partner in (client, pro):
            raise serializers.ValidationError({"partner": "Choisis une autre personne."})
        if attrs["payment_method"] != Booking.Method.CASH:
            raise serializers.ValidationError(
                {"payment_method": "Le paiement mobile n'est pas encore disponible : choisis « Sur place »."}
            )

        end = start + timedelta(minutes=service.duration_min)
        lead_hours = cfg().booking_lead_hours
        if start < timezone.now() + timedelta(hours=lead_hours):
            raise serializers.ValidationError({"starts_at": f"Réserve au moins {lead_hours} h à l'avance." if lead_hours else "Cette heure est passée."})
        if not slots.inside_availability(pro, start, end):
            raise serializers.ValidationError({"starts_at": "Ce coach n'est pas disponible à cette heure."})
        if slots.overlaps(pro, start, end):
            raise serializers.ValidationError({"starts_at": "Ce créneau vient d'être pris. Choisis-en un autre."})

        attrs.update(pro=pro, ends_at=end, mode=mode)
        return attrs
