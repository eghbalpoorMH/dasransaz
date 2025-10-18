from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from config.settings.env import BASE_DIR, settings


# General ---------------------------------------------------------------------
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True
SITE_ID = 1

DEBUG = settings.debug
SECRET_KEY = settings.secret_key
ALLOWED_HOSTS = settings.allowed_hosts

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "storages",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]


# Database --------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": settings.database_name,
        "USER": settings.database_user,
        "PASSWORD": settings.database_password,
        "HOST": settings.database_host,
        "PORT": settings.database_port,
    }
}


# Authentication & DRF -------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=settings.jwt_access_token_lifetime_minutes),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=settings.jwt_refresh_token_lifetime_days),
    "ROTATE_REFRESH_TOKENS": settings.jwt_rotation_strategy == "rotate",
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# API Docs --------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Storyteller API",
    "DESCRIPTION": "API documentation for the Storyteller service.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
}


# Static & Media via Arvan ----------------------------------------------------
AWS_ACCESS_KEY_ID = settings.arvan_access_key_id
AWS_SECRET_ACCESS_KEY = settings.arvan_secret_access_key
AWS_S3_ENDPOINT_URL = str(settings.arvan_endpoint_url)
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = settings.arvan_signed_url_expiry_seconds
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_FILE_OVERWRITE = False

ARVAN_STATIC_BUCKET = settings.arvan_static_bucket
ARVAN_MEDIA_BUCKET = settings.arvan_media_bucket
ARVAN_STATIC_LOCATION = settings.arvan_static_location
ARVAN_MEDIA_LOCATION = settings.arvan_media_location

_endpoint = urlparse(AWS_S3_ENDPOINT_URL)
_default_static_domain = f"{settings.arvan_static_bucket}.{_endpoint.netloc}"
_default_media_domain = f"{settings.arvan_media_bucket}.{_endpoint.netloc}"

ARVAN_STATIC_CUSTOM_DOMAIN = settings.arvan_static_custom_domain or _default_static_domain
ARVAN_MEDIA_CUSTOM_DOMAIN = settings.arvan_media_custom_domain or _default_media_domain

STATIC_URL = f"https://{ARVAN_STATIC_CUSTOM_DOMAIN}/{ARVAN_STATIC_LOCATION}/"
MEDIA_URL = f"https://{ARVAN_MEDIA_CUSTOM_DOMAIN}/{ARVAN_MEDIA_LOCATION}/"

STATICFILES_DIRS = [BASE_DIR / "static"]

STATICFILES_STORAGE = "config.storage_backends.PublicStaticStorage"
DEFAULT_FILE_STORAGE = "config.storage_backends.PrivateMediaStorage"


# CORS & CSRF -----------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [str(origin) for origin in settings.cors_allowed_origins]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [str(origin) for origin in settings.csrf_trusted_origins]


# Celery ----------------------------------------------------------------------
CELERY_BROKER_URL = settings.broker_url
CELERY_RESULT_BACKEND = settings.result_backend
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE


# Logging ---------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": settings.log_level,
    },
}
# Authentication helpers ------------------------------------------------------
AUTH_VERIFICATION_CODE_LENGTH = settings.verification_code_length
AUTH_VERIFICATION_CODE_EXPIRY_MINUTES = settings.verification_code_expiry_minutes
KAVENEGAR_API_KEY = settings.kavenegar_api_key
KAVENEGAR_SENDER = settings.kavenegar_sender
KAVENEGAR_TEMPLATE = settings.kavenegar_template
