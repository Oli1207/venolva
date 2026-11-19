"""Corrections d'identité et de texte faites depuis l'administration."""
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.accounts.models import User, normalize_email

from .models import audit

def edit_identity(admin, user, data) -> str | None:
    """Corrige l'e-mail, le nom ou la commune d'un compte. Renvoie un message d'erreur ou None."""
    changes = {}
    if "email" in data:
        try:
            email = normalize_email(str(data["email"] or ""))
        except DjangoValidationError as exc:
            return exc.messages[0]
        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            return "Cet e-mail est déjà utilisé par un autre compte."
        changes["email"] = [user.email, email]
        user.email = email
    for field, size in (("display_name", 60), ("commune", 60)):
        if field in data:
            value = str(data[field] or "").strip()[:size]
            changes[field] = [getattr(user, field), value]
            setattr(user, field, value)
    if changes:
        user.save()
        audit(admin, "user.identity", f"user:{user.id}", changes=changes)
    return None


def edit_gym_text(admin, gym, data) -> str | None:
    changes = {}
    for field, size, required in (("name", 120, True), ("commune", 60, True), ("address", 200, False), ("description", 500, False)):
        if field in data:
            value = str(data[field] or "").strip()[:size]
            if required and not value:
                return f"« {field} » ne peut pas être vide."
            changes[field] = [getattr(gym, field), value]
            setattr(gym, field, value)
    if changes:
        gym.save()
        audit(admin, "gym.text", f"gym:{gym.id}", changes=changes)
    return None
