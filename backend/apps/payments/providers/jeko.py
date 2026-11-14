"""Client Jeko (Partner API) : mobile money (Wave, Orange, MTN, Moov, Djamo) par redirection.

Montants en centimes, authentification par X-API-KEY et X-API-KEY-ID. Le paiement est confirmé par webhook signé."""
import hashlib
import hmac
import logging
from urllib.parse import quote

import requests
from django.conf import settings

from ..exceptions import PaymentUnavailable

logger = logging.getLogger(__name__)

NAME = "jeko"
METHODS = ("wave", "orange", "mtn", "moov", "djamo")


def is_configured() -> bool:
    return bool(settings.JEKO_API_KEY and settings.JEKO_API_KEY_ID and settings.JEKO_STORE_ID)


def _call(method, path, **kwargs):
    if not is_configured():
        raise PaymentUnavailable()
    headers = {"X-API-KEY": settings.JEKO_API_KEY, "X-API-KEY-ID": settings.JEKO_API_KEY_ID, "Content-Type": "application/json"}
    try:
        response = requests.request(method, f"{settings.JEKO_BASE_URL}/partner_api{path}", headers=headers, timeout=settings.JEKO_TIMEOUT_SECONDS, **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
    except requests.RequestException:
        logger.exception("Appel Jeko en échec : %s %s", method, path)
        raise PaymentUnavailable()
    if response.status_code >= 400:
        # Seul un identifiant d'erreur sans donnée personnelle est journalisé.
        logger.error("Jeko a refusé %s %s (HTTP %s, %s)", method, path, response.status_code, str(payload.get("error") or payload.get("code") or "")[:80])
        raise PaymentUnavailable()
    return payload


def to_cents(amount_fcfa: int) -> int:
    return int(amount_fcfa) * 100


def create_payment_request(*, amount_fcfa, reference, success_url, error_url, method="jeko") -> dict:
    """Renvoie {id, redirectUrl, ...}. method='jeko' laisse choisir le moyen sur la page Jeko."""
    return _call(
        "POST", "/payment_requests",
        json={
            "storeId": settings.JEKO_STORE_ID,
            "amountCents": to_cents(amount_fcfa),
            "currency": settings.JEKO_CURRENCY,
            "reference": reference,
            "paymentDetails": {"type": "redirect", "data": {"paymentMethod": method, "successUrl": success_url, "errorUrl": error_url}},
        },
    )


def get_payment_request(payment_request_id) -> dict:
    return _call("GET", f"/payment_requests/{quote(str(payment_request_id), safe='')}")


def is_valid_signature(raw_body: bytes, signature: str) -> bool:
    """Jeko-Signature : HMAC-SHA256 du corps brut, en hexadécimal minuscule."""
    secret = settings.JEKO_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())
