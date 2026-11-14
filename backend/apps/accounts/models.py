import re

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

PHONE_RE = re.compile(r"^\+225\d{10}$")


def normalize_phone(raw: str) -> str:
    """Accepte 07 00 00 00 00, 0700000000, +2250700000000 et renvoie +2250700000000."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("00225"):
        digits = "+" + digits[2:]
    elif digits.startswith("225") and len(digits) == 13:
        digits = "+" + digits
    elif not digits.startswith("+") and len(digits) == 10:
        digits = "+225" + digits
    if not PHONE_RE.match(digits):
        raise ValidationError("Numéro ivoirien invalide : 10 chiffres attendus.")
    return digits


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        phone = normalize_phone(phone)
        user = self.model(phone=phone, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Un seul compte pour tout le monde. Le statut pro s'ajoute dessus."""

    class ProType(models.TextChoices):
        COACH = "coach", "Coach sportif"
        GYM = "gym", "Salle de sport"
        NUTRITION = "nutrition", "Nutritionniste, diététicien"
        PHYSIO = "physio", "Kinésithérapeute"
        DOCTOR = "doctor", "Médecin du sport"
        SHOP = "shop", "Boutique de matériel"

    phone = models.CharField(max_length=14, unique=True)
    display_name = models.CharField(max_length=60, blank=True)
    commune = models.CharField(max_length=60, blank=True)
    pro_type = models.CharField(max_length=12, choices=ProType.choices, blank=True)
    pro_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()
    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    def __str__(self):
        return self.display_name or self.phone

    @property
    def initials(self) -> str:
        parts = (self.display_name or "").split()
        return "".join(p[0] for p in parts[:2]).upper() or "?"


class Profile(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "debutant", "Débutant"
        INTERMEDIATE = "intermediaire", "Intermédiaire"
        ADVANCED = "avance", "Avancé"

    GOALS = {
        "weight_loss": "Perdre du poids",
        "muscle": "Prendre du muscle",
        "restart": "Me remettre au sport",
        "cardio": "Cardio et endurance",
        "combat": "Sports de combat",
        "dance": "Danse et fitness",
    }
    PERIODS = ("morning", "noon", "evening", "weekend")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    goals = models.JSONField(default=list, blank=True)  # codes de GOALS, deux au maximum
    level = models.CharField(max_length=14, choices=Level.choices, default=Level.BEGINNER)
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    days = models.JSONField(default=list, blank=True)  # 0 = lundi ... 6 = dimanche
    periods = models.JSONField(default=list, blank=True)  # codes de PERIODS
    outdoor = models.BooleanField(default=False)
    bio = models.CharField(max_length=240, blank=True)
    birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
    visible = models.BooleanField(default=True)
    show_punctuality = models.BooleanField(default=True)
    onboarded = models.BooleanField(default=False)

    def clean(self):
        if len(self.goals) > 2 or any(g not in self.GOALS for g in self.goals):
            raise ValidationError({"goals": "Deux objectifs au maximum, parmi la liste proposée."})
        if any(not isinstance(d, int) or not 0 <= d <= 6 for d in self.days):
            raise ValidationError({"days": "Jours invalides."})
        if any(p not in self.PERIODS for p in self.periods):
            raise ValidationError({"periods": "Créneaux invalides."})

    def __str__(self):
        return f"Profil de {self.user}"


class OtpCode(models.Model):
    """Code à usage unique envoyé par SMS ou WhatsApp. Seul un hash est stocké."""

    phone = models.CharField(max_length=14, db_index=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
