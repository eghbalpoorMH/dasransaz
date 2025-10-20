from django.apps import AppConfig


class RequestsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "story_requests"
    label = "requests"
    verbose_name = "Story Requests"

    def ready(self) -> None:  # pragma: no cover - import side effects
        from . import signals  # noqa: F401
