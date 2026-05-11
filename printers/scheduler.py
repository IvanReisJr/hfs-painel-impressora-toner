"""APScheduler configuration: runs collect_toner every day at 07:00."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_collection():
    """Job function executed by the scheduler."""
    from printers.services.collector import collect_all_active
    results = collect_all_active()
    ok = sum(1 for r in results if r.success)
    logger.info("Scheduler: %d/%d printers collected successfully", ok, len(results))


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(
        jobstores={"default": MemoryJobStore()},
        timezone="America/Sao_Paulo",
    )

    _scheduler.add_job(
        _run_collection,
        trigger=CronTrigger(hour=7, minute=0),
        id="daily_toner_collection",
        name="Coleta diária de toner",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("APScheduler started — daily collection at 07:00 (America/Sao_Paulo)")
