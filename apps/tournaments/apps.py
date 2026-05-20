from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tournaments"

    def ready(self) -> None:
        import apps.tournaments.signals  # noqa: F401
