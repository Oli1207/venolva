"""Réglages Django de Venolva."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEV_SECRET_KEY = "dev-only-secret-key-change-me-before-production-0123456789"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEV_SECRET_KEY)
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
if not DEBUG and (SECRET_KEY == DEV_SECRET_KEY or len(SECRET_KEY) < 40):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("En production (DJANGO_DEBUG=0), définis DJANGO_SECRET_KEY avec une valeur secrète d'au moins 40 caractères.")
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
    "apps.ambassadors",
    "apps.safety",
    "apps.promo",
    "apps.notifications",
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
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
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
PAYMENT_EMAIL_DOMAIN = os.getenv("PAYMENT_EMAIL_DOMAIN", "pay.venolva.app")  # repli si un membre n'a pas d'e-mail (ex. compte ancien)
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


# E-mail : le code de connexion part par ici. En développement il s'affiche dans la console ;
# en production, renseigne EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend et les variables EMAIL_*.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Venolva <no-reply@venolva.app>")


# --- Production ------------------------------------------------------------------------------------------------------
# Derrière nginx (HTTPS) : DJANGO_DEBUG=0 active la redirection HTTPS, les cookies sécurisés et HSTS.
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_REFERRER_POLICY = "same-origin"
    # L'interface navigable de DRF n'est utile qu'en développement.
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = ("rest_framework.renderers.JSONRenderer",)
    # Derrière nginx, l'adresse IP du visiteur vient de X-Forwarded-For : sans cela, tout le monde partagerait la même limite (127.0.0.1).
    REST_FRAMEWORK["NUM_PROXIES"] = int(os.getenv("DJANGO_NUM_PROXIES", "1"))

# Cache (limites de requêtes) : partagé entre les processus gunicorn. Redis si REDIS_URL, sinon la base de données
# (créer la table une fois : manage.py createcachetable). En développement, un cache en mémoire suffit.
if os.getenv("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": os.environ["REDIS_URL"]}}
elif not DEBUG:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "venolva_cache"}}

# Photos : stockage objet compatible S3 (DigitalOcean Spaces) si AWS_STORAGE_BUCKET_NAME est défini, sinon le disque.
if os.getenv("AWS_STORAGE_BUCKET_NAME"):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": os.environ["AWS_STORAGE_BUCKET_NAME"],
                "access_key": os.environ["AWS_ACCESS_KEY_ID"],
                "secret_key": os.environ["AWS_SECRET_ACCESS_KEY"],
                "endpoint_url": os.environ["AWS_S3_ENDPOINT_URL"],  # ex. https://fra1.digitaloceanspaces.com
                "region_name": os.getenv("AWS_S3_REGION_NAME", ""),
                "custom_domain": os.getenv("AWS_S3_CUSTOM_DOMAIN") or None,  # ex. cdn.venolva.app
                "default_acl": "public-read",
                "querystring_auth": False,
                "file_overwrite": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
}
