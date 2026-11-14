"""Réglages Django de Djinzin."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key-change-me-before-production-0123456789")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.accounts",
    "apps.gyms",
    "apps.matching",
    "apps.meetups",
    "apps.chat",
    "apps.feed",
    "apps.pros",
    "apps.market",
    "apps.payments",
    "apps.backoffice",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL si DATABASE_URL est défini par variables, sinon SQLite en local.
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Photos d'annonces. En production, à remplacer par un stockage objet (Cloudinary, S3).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Par adresse IP. Une limite par numéro s'ajoute dans OtpRequestView.
    "DEFAULT_THROTTLE_RATES": {
        "otp_request": "20/hour", "otp_verify": "40/hour",
        "payment_init": "30/hour", "payment_webhook": "600/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=60),
}

CORS_ALLOWED_ORIGINS = [
    o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o
]

# --- Paiement en ligne : Jeko (mobile money) et Paystack (carte, et mobile money en repli) ---------------------------
# Les clés viennent de l'environnement (backend/.env, jamais dans git). Sans clés, le paiement en ligne est simplement indisponible.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
PAYMENT_EMAIL_DOMAIN = os.getenv("PAYMENT_EMAIL_DOMAIN", "pay.djinzin.app")  # Paystack exige un e-mail, les membres n'ont qu'un numéro
# Commission, mode de paiement et autres réglages métier : modifiables dans l'administration de l'app (PlatformSettings).

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_WEBHOOK_SECRET = os.getenv("PAYSTACK_WEBHOOK_SECRET", "") or PAYSTACK_SECRET_KEY  # Paystack signe avec la clé secrète
PAYSTACK_BASE_URL = os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co")
PAYSTACK_CURRENCY = os.getenv("PAYSTACK_CURRENCY", "XOF")
PAYSTACK_TIMEOUT_SECONDS = 15

JEKO_BASE_URL = os.getenv("JEKO_BASE_URL", "https://api.jeko.africa")
JEKO_API_KEY = os.getenv("JEKO_API_KEY", "")
JEKO_API_KEY_ID = os.getenv("JEKO_API_KEY_ID", "")
JEKO_STORE_ID = os.getenv("JEKO_STORE_ID", "")
JEKO_WEBHOOK_SECRET = os.getenv("JEKO_WEBHOOK_SECRET", "")
JEKO_CURRENCY = os.getenv("JEKO_CURRENCY", "XOF")
JEKO_TIMEOUT_SECONDS = 15

# Code de connexion : en dev il est affiché dans la console, aucun SMS n'est envoyé.
OTP_DEV_ECHO = DEBUG
