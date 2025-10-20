from django.apps import AppConfig


class StoriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stories"
    verbose_name = "Stories"

    def ready(self) -> None:  # pragma: no cover - import side effects
        from . import signals  # noqa: F401
