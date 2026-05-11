import os

import dj_database_url

from .base import *  # noqa: F401, F403

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = False

ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")

CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

DATABASES = {"default": dj_database_url.config(conn_max_age=600)}

CELERY_BROKER_URL = os.environ["REDIS_URL"]
CELERY_RESULT_BACKEND = os.environ["REDIS_URL"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
