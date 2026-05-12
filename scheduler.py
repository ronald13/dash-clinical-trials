import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler(engine, cache):
    """Start background S3-polling scheduler. Safe to call multiple times."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)

    def _check_s3():
        changed = engine.reload_if_changed()
        if changed:
            cache.clear()
            logger.info("S3 data changed — cache cleared")

    _scheduler.add_job(
        _check_s3, "interval", minutes=10,
        id="s3_poll", misfire_grace_time=60,
    )
    _scheduler.start()
    logger.info("S3 polling scheduler started (interval=10 min)")
    return _scheduler
