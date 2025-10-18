from __future__ import annotations

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class PublicStaticStorage(S3Boto3Storage):
    """Publicly readable static files served via Arvan."""

    bucket_name = settings.ARVAN_STATIC_BUCKET
    location = settings.ARVAN_STATIC_LOCATION
    default_acl = "public-read"
    querystring_auth = False
    custom_domain = settings.ARVAN_STATIC_CUSTOM_DOMAIN


class PrivateMediaStorage(S3Boto3Storage):
    """Private media files that require signed URLs."""

    bucket_name = settings.ARVAN_MEDIA_BUCKET
    location = settings.ARVAN_MEDIA_LOCATION
    default_acl = "private"
    file_overwrite = False
    custom_domain = settings.ARVAN_MEDIA_CUSTOM_DOMAIN
    querystring_auth = True
