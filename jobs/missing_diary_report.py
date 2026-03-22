import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from api.state import missing_report_state
from config import config
from services.rd_obras import (
    fetch_all_projects,
    filter_active_projects,
    fetch_today_diaries,
)
from services.wts_chat import send_whatsapp_message
from services.report_builder import build_missing_report

logger = logging.getLogger(__name__)


async def run_missing_diary_report() -> None:
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz=tz)
    today = now.date()
    date_str = today.strftime("%d/%m/%Y")
    generated_at = now.strftime("%H:%M")

    logger.info("=== Missing diary report job started — %s ===", date_str)

    run = missing_report_state.start_run()
    projects_count = 0
    missing_count = 0

    try:
        async with httpx.AsyncClient(timeout=config.http_timeout) as client:
            try:
                all_projects = await fetch_all_projects(client)
            except Exception as exc:
                logger.error("Failed to fetch projects: %s", exc)
                missing_report_state.finish_run(run, success=False, projects=0, missing=0, error=str(exc))
                return

            active_projects = filter_active_projects(all_projects)
            if not active_projects:
                logger.warning("No active projects to process")
                missing_report_state.finish_run(run, success=False, projects=0, missing=0, error="Nenhum projeto ativo")
                return

            projects_count = len(active_projects)
            missing_projects = []

            tasks = [
                fetch_today_diaries(client, proj.id, today)
                for proj in active_projects
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for proj, result in zip(active_projects, results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch diaries for '%s': %s", proj.name, result)
                # Treat as missing when we can't determine diary status
                missing_projects.append(proj)
            elif not result:
                logger.info("No diary today for project '%s'", proj.name)
                missing_projects.append(proj)
            else:
                logger.debug("Project '%s' has %d diary(ies) today", proj.name, len(result))

        missing_count = len(missing_projects)
        logger.info(
            "Checked %d project(s): %d missing diary(ies)",
            projects_count,
            missing_count,
        )

        message = build_missing_report(missing_projects, projects_count, date_str, generated_at)
        success = await send_whatsapp_message(message)

        if success:
            logger.info("=== Missing diary report sent successfully ===")
        else:
            logger.error("=== Missing diary report FAILED to send ===")

        missing_report_state.finish_run(
            run,
            success=success,
            projects=projects_count,
            missing=missing_count,
            error=None if success else "Falha ao enviar via WTS Chat",
        )

    except Exception as exc:
        logger.exception("Unexpected error in missing diary report job: %s", exc)
        missing_report_state.finish_run(run, success=False, projects=projects_count, missing=missing_count, error=str(exc))


def run_missing_diary_report_sync() -> None:
    asyncio.run(run_missing_diary_report())
