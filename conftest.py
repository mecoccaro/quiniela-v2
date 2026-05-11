from django.conf import settings


def pytest_configure() -> None:
    settings.DJANGO_SETTINGS_MODULE = "quiniela.settings.local"
