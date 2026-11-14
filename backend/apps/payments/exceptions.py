from rest_framework import status
from rest_framework.exceptions import APIException


class PaymentUnavailable(APIException):
    """Le prestataire ne répond pas ou refuse. Le détail technique n'est jamais renvoyé au client."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Le paiement en ligne est momentanément indisponible. Réessaie dans un instant, ou paie sur place."
    default_code = "payment_unavailable"
