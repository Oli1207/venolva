"""Validation et ré-encodage des photos d'annonces."""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers

MAX_BYTES = 6 * 1024 * 1024
MAX_SIDE = 1600
ALLOWED = {"JPEG", "PNG", "WEBP"}


def clean_image(upload) -> ContentFile:
    """Vérifie que le fichier est une vraie image, la redresse, la réduit et la ré-encode en JPEG.

    Le ré-encodage supprime les métadonnées EXIF, dont la position GPS de la photo."""
    if upload.size > MAX_BYTES:
        raise serializers.ValidationError("Photo trop lourde (6 Mo au maximum).")
    try:
        img = Image.open(upload)
        if img.format not in ALLOWED:
            raise serializers.ValidationError("Formats acceptés : JPEG, PNG ou WebP.")
        img.load()
    except (UnidentifiedImageError, OSError):
        raise serializers.ValidationError("Ce fichier n'est pas une image valide.")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)
    return ContentFile(out.getvalue(), name="photo.jpg")
