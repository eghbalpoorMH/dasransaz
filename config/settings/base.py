from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

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
    "billing",
    "story_requests",
    "stories",
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


BILLING = {
    "CURRENCY": settings.billing_currency,
    "DEFAULT_PROVIDER": settings.billing_default_provider,
    "PROVIDERS": settings.billing_providers
    or {
        "iran_gw": {
            "MERCHANT_ID": "",
            "GATEWAY": "zarinpal",
            "SANDBOX": True,
        },
        "bazaar_iap": {
            "CLIENT_ID": "",
            "CLIENT_SECRET": "",
            "PACKAGE_NAME": "",
            "REFRESH_TOKEN": "",
            "SANDBOX": True,
        },
    },
}


# Static & Media via Arvan ----------------------------------------------------
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 1000
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_FILE_OVERWRITE = False
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}


def _build_public_url(endpoint_url: str, bucket_name: str, location: str) -> str:
    endpoint = (endpoint_url or "").strip()
    bucket = (bucket_name or "").strip()
    location = (location or "").strip()
    if not endpoint:
        return ""

    parsed = urlsplit(endpoint.rstrip("/"))
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    bucket_in_subdomain = bool(bucket) and parsed.netloc.startswith(f"{bucket}.")
    bucket_in_path = bool(bucket) and bucket in path_segments

    combined_path = path_segments.copy()
    if bucket and not bucket_in_subdomain and not bucket_in_path:
        combined_path.append(bucket)
    if location:
        combined_path.extend([segment for segment in location.split("/") if segment])

    new_path = "/" + "/".join(combined_path) if combined_path else ""
    rebuilt = urlunsplit((parsed.scheme, parsed.netloc, new_path, "", ""))
    return rebuilt.rstrip("/") + "/"


PUBLIC_ACCESS_KEY = settings.s3_access_key_public or settings.arvan_access_key_id
PUBLIC_SECRET_KEY = settings.s3_secret_key_public or settings.arvan_secret_access_key
PUBLIC_BUCKET_NAME = settings.s3_bucket_name_public or settings.arvan_media_bucket
PUBLIC_LOCATION = settings.s3_location_public or settings.arvan_media_location
PUBLIC_ENDPOINT_URL = settings.s3_endpoint_url_public or str(settings.arvan_endpoint_url)

STATIC_ACCESS_KEY = settings.s3_access_key_static or settings.arvan_access_key_id
STATIC_SECRET_KEY = settings.s3_secret_key_static or settings.arvan_secret_access_key
STATIC_BUCKET_NAME = settings.s3_bucket_name_static or settings.arvan_static_bucket
STATIC_LOCATION = settings.s3_location_static or settings.arvan_static_location
STATIC_ENDPOINT_URL = settings.s3_endpoint_url_static or str(settings.arvan_endpoint_url)

STATIC_URL = _build_public_url(STATIC_ENDPOINT_URL, STATIC_BUCKET_NAME, STATIC_LOCATION)
MEDIA_URL = _build_public_url(PUBLIC_ENDPOINT_URL, PUBLIC_BUCKET_NAME, PUBLIC_LOCATION)

STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": PUBLIC_ACCESS_KEY,
            "secret_key": PUBLIC_SECRET_KEY,
            "bucket_name": PUBLIC_BUCKET_NAME,
            "file_overwrite": False,
            "location": PUBLIC_LOCATION,
            "endpoint_url": PUBLIC_ENDPOINT_URL,
            "querystring_expire": 1000,
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": STATIC_ACCESS_KEY,
            "secret_key": STATIC_SECRET_KEY,
            "bucket_name": STATIC_BUCKET_NAME,
            "default_acl": "public-read",
            "file_overwrite": False,
            "location": STATIC_LOCATION,
            "endpoint_url": STATIC_ENDPOINT_URL,
            "querystring_auth": False,
        },
    },
}

AWS_ACCESS_KEY_ID = PUBLIC_ACCESS_KEY
AWS_SECRET_ACCESS_KEY = PUBLIC_SECRET_KEY
AWS_S3_ENDPOINT_URL = PUBLIC_ENDPOINT_URL


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
