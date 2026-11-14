"""Client Paystack : paiement par redirection vers la page hébergée, confirmé par webhook signé."""
import hashlib
import hmac
import logging
from urllib.parse import quote

import requests
from django.conf import settings

from ..exceptions import PaymentUnavailable

logger = logging.getLogger(__name__)

NAME = "paystack"


def is_configured() -> bool:
    return bool(settings.PAYSTACK_SECRET_KEY)


def _call(method, path, **kwargs):
    if not is_configured():
        raise PaymentUnavailable()
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.request(method, f"{settings.PAYSTACK_BASE_URL}{path}", headers=headers, timeout=settings.PAYSTACK_TIMEOUT_SECONDS, **kwargs)
        payload = response.json()
    except (requests.RequestException, ValueError):
        logger.exception("Appel Paystack en échec : %s %s", method, path)
        raise PaymentUnavailable()
    if response.status_code >= 400 or not payload.get("status"):
        # Le message de Paystack n'est pas renvoyé au client : il peut contenir des détails internes.
        logger.error("Paystack a refusé %s %s (HTTP %s)", method, path, response.status_code)
        raise PaymentUnavailable()
    return payload["data"]


def to_subunits(amount_fcfa: int) -> int:
    return int(amount_fcfa) * 100


def initialize(*, email, amount_fcfa, reference, callback_url, metadata=None) -> dict:
    """Renvoie {authorization_url, access_code, reference}."""
    return _call(
        "POST", "/transaction/initialize",
        json={
            "email": email, "amount": to_subunits(amount_fcfa), "currency": settings.PAYSTACK_CURRENCY,
            "reference": reference, "callback_url": callback_url, "metadata": metadata or {},
        },
    )


def verify(reference) -> dict:
    return _call("GET", f"/transaction/verify/{quote(reference, safe='')}")


def is_valid_signature(raw_body: bytes, signature: str) -> bool:
    secret = settings.PAYSTACK_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
