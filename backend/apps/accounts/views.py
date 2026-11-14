import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
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


def hash_code(phone: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


class OtpRequestView(APIView):
    """Envoie un code à 6 chiffres. Le fournisseur SMS/WhatsApp se branche dans `send_code`."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    @staticmethod
    def send_code(phone: str, code: str):
        # À remplacer par l'envoi réel (SMS ou WhatsApp). En dev, on l'écrit dans la console.
        log.warning("Code de connexion pour %s : %s", phone, code)

    def post(self, request):
        ser = OtpRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = ser.validated_data["phone"]
        recent = OtpCode.objects.filter(phone=phone, created_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= cfg().otp_max_requests_per_hour:
            return Response(
                {"detail": "Trop de demandes pour ce numéro. Réessaie dans une heure."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction.atomic():
            OtpCode.objects.filter(phone=phone, used=False).update(used=True)
            OtpCode.objects.create(phone=phone, code_hash=hash_code(phone, code))
        self.send_code(phone, code)
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
        phone, code = ser.validated_data["phone"], ser.validated_data["code"]
        otp = OtpCode.objects.filter(phone=phone, used=False).first()
        expired = otp and otp.created_at < timezone.now() - timedelta(seconds=cfg().otp_ttl_seconds)
        if not otp or expired or otp.attempts >= cfg().otp_max_attempts:
            return Response({"detail": "Code expiré. Demande-en un nouveau."}, status=status.HTTP_400_BAD_REQUEST)
        otp.attempts += 1
        if not hmac.compare_digest(otp.code_hash, hash_code(phone, code)):
            otp.save(update_fields=["attempts"])
            return Response({"detail": "Code incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        otp.used = True
        otp.save(update_fields=["used", "attempts"])

        user, created = User.objects.get_or_create(phone=phone)
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
