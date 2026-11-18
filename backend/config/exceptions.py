from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Un identifiant mal formé (ex. /membres/abc) répond 400 au lieu de faire planter le serveur."""
    if isinstance(exc, DjangoValidationError):
        return Response({"detail": exc.messages[0] if exc.messages else "Valeur invalide."}, status=status.HTTP_400_BAD_REQUEST)
    return exception_handler(exc, context)
