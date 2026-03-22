import logging
import signal
import sys
import threading

import uvicorn
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api.app import app
from api.state import app_state
from config import config
from jobs.daily_report import run_daily_report_sync
from jobs.missing_diary_report import run_missing_diary_report_sync

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _start_scheduler() -> BackgroundScheduler:
    tz = pytz.timezone(config.timezone)
    scheduler = BackgroundScheduler(timezone=tz)

    scheduler.add_job(
        run_daily_report_sync,
        trigger=CronTrigger(
            hour=config.report_hour,
            minute=config.report_minute,
            timezone=tz,
        ),
        id="daily_report",
        name="Daily RD Obras WhatsApp Report",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    scheduler.add_job(
        run_missing_diary_report_sync,
        trigger=CronTrigger(
            hour=config.missing_report_hour,
            minute=config.missing_report_minute,
            timezone=tz,
        ),
        id="missing_diary_report",
        name="Missing Diary WhatsApp Report",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    app_state.scheduler = scheduler

    logger.info(
        "Scheduler started — daily report at %02d:%02d, missing diary report at %02d:%02d (%s)",
        config.report_hour,
        config.report_minute,
        config.missing_report_hour,
        config.missing_report_minute,
        config.timezone,
    )
    return scheduler


def main():
    scheduler = _start_scheduler()

    def _shutdown(signum, frame):
        logger.info("Signal %d received — shutting down", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    if "--run-now" in sys.argv:
        logger.info("--run-now flag detected: running report immediately in background")
        threading.Thread(target=run_daily_report_sync, daemon=True).start()

    if "--run-now-missing" in sys.argv:
        logger.info("--run-now-missing flag detected: running missing diary report immediately in background")
        threading.Thread(target=run_missing_diary_report_sync, daemon=True).start()

    logger.info(
        "FastAPI + Swagger disponível em http://0.0.0.0:%d/docs",
        config.health_check_port,
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.health_check_port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
