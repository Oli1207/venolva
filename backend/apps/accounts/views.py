import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.backoffice.config import cfg

from .models import OtpCode, Profile, User
from .serializers import MeSerializer, OtpRequestSerializer, OtpVerifySerializer

log = logging.getLogger(__name__)


def hash_code(email: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


class OtpRequestView(APIView):
    """Envoie un code à 6 chiffres. Le fournisseur SMS/WhatsApp se branche dans `send_code`."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    @staticmethod
    def send_code(email: str, code: str):
        """Envoie le code par e-mail. En développement le backend e-mail écrit le message dans la console."""
        minutes = max(1, cfg().otp_ttl_seconds // 60)
        send_mail(
            subject=f"Ton code Venolva : {code}",
            message=f"Ton code de connexion Venolva est {code}.\n\nIl est valable {minutes} minutes. Si tu n'as rien demandé, ignore ce message.",
            from_email=None,
            recipient_list=[email],
        )

    def post(self, request):
        ser = OtpRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        recent = OtpCode.objects.filter(email=email, created_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= cfg().otp_max_requests_per_hour:
            return Response(
                {"detail": "Trop de demandes pour cette adresse. Réessaie dans une heure."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction.atomic():
            OtpCode.objects.filter(email=email, used=False).update(used=True)
            OtpCode.objects.create(email=email, code_hash=hash_code(email, code))
        try:
            self.send_code(email, code)
        except Exception:  # noqa: BLE001 : le détail (serveur, identifiants) ne doit pas fuiter
            log.exception("Envoi du code par e-mail impossible")
            return Response({"detail": "Impossible d'envoyer l'e-mail pour le moment. Réessaie dans un instant."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        body = {"detail": "Code envoyé."}
        if settings.OTP_DEV_ECHO:
            body["dev_code"] = code
        return Response(body)


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        ser = OtpVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email, code = ser.validated_data["email"], ser.validated_data["code"]
        otp = OtpCode.objects.filter(email=email, used=False).first()
        expired = otp and otp.created_at < timezone.now() - timedelta(seconds=cfg().otp_ttl_seconds)
        if not otp or expired or otp.attempts >= cfg().otp_max_attempts:
            return Response({"detail": "Code expiré. Demande-en un nouveau."}, status=status.HTTP_400_BAD_REQUEST)
        otp.attempts += 1
        if not hmac.compare_digest(otp.code_hash, hash_code(email, code)):
            otp.save(update_fields=["attempts"])
            return Response({"detail": "Code incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        otp.used = True
        otp.save(update_fields=["used", "attempts"])

        user, created = User.objects.get_or_create(email=email)
        Profile.objects.get_or_create(user=user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "created": created,
                "user": MeSerializer(user).data,
            }
        )


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        ser = MeSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request):
        """DELETE avec {confirm: "SUPPRIMER"} : efface mes données personnelles (les paiements restent, anonymisés)."""
        from .deletion import anonymize, blockers

        if request.data.get("confirm") != "SUPPRIMER":
            return Response({"detail": "Écris SUPPRIMER pour confirmer."}, status=status.HTTP_400_BAD_REQUEST)
        reasons = blockers(request.user)
        if reasons:
            return Response({"detail": reasons[0], "reasons": reasons}, status=status.HTTP_409_CONFLICT)
        anonymize(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
