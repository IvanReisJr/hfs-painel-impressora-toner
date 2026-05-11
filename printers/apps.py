"""App config with APScheduler startup for automatic daily collection."""

import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PrintersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "printers"
    verbose_name = "Impressoras"

    def ready(self):
        """Start the background scheduler when Django starts (non-test mode)."""
        import sys
        # Only run scheduler in the main process, not during tests or migrations
        if "test" in sys.argv or "migrate" in sys.argv or "makemigrations" in sys.argv:
            return
        try:
            from printers.scheduler import start_scheduler
            start_scheduler()
        except Exception as exc:
            logger.warning("Scheduler not started: %s", exc)
