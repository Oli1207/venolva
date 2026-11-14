from rest_framework import serializers

from .models import Profile, User, normalize_phone
from django.core.exceptions import ValidationError as DjangoValidationError


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        try:
            return normalize_phone(super().to_internal_value(data))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0])


class OtpRequestSerializer(serializers.Serializer):
    phone = PhoneField()


class OtpVerifySerializer(serializers.Serializer):
    phone = PhoneField()
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Le code contient 6 chiffres."})


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "goals", "level", "gym", "days", "periods", "outdoor", "bio",
            "birth_year", "visible", "show_punctuality", "onboarded",
        ]

    def validate_goals(self, value):
        if len(value) > 2 or any(g not in Profile.GOALS for g in value):
            raise serializers.ValidationError("Deux objectifs au maximum, parmi la liste proposée.")
        return value

    def validate_days(self, value):
        if any(not isinstance(d, int) or not 0 <= d <= 6 for d in value):
            raise serializers.ValidationError("Jours invalides (0 = lundi, 6 = dimanche).")
        return sorted(set(value))

    def validate_periods(self, value):
        if any(p not in Profile.PERIODS for p in value):
            raise serializers.ValidationError("Créneau invalide.")
        return sorted(set(value))


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "phone", "display_name", "commune", "initials", "pro_type", "pro_verified", "is_staff", "profile"]
        read_only_fields = ["id", "phone", "pro_type", "pro_verified", "is_staff"]

    def update(self, instance, validated):
        profile_data = validated.pop("profile", None)
        for key, value in validated.items():
            setattr(instance, key, value)
        instance.save()
        if profile_data is not None:
            for key, value in profile_data.items():
                setattr(instance.profile, key, value)
            instance.profile.save()
        return instance
