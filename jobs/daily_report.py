import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from api.state import app_state
from config import config
from models.schemas import ReportData
from services.rd_obras import (
    fetch_all_projects,
    filter_active_projects,
    fetch_today_diaries,
    fetch_diary_detail,
)
from services.llm import summarize_comments
from services.wts_chat import send_whatsapp_message
from services.report_builder import build_report

logger = logging.getLogger(__name__)


async def _process_project(
    client: httpx.AsyncClient,
    project_id: str,
    project_name: str,
    today,
) -> list:
    details = []
    try:
        diaries = await fetch_today_diaries(client, project_id, today)
        if not diaries:
            logger.debug("No diary today for project '%s'", project_name)
            return details

        logger.info("Project '%s': found %d diary(ies) today", project_name, len(diaries))
        for diary in diaries:
            await asyncio.sleep(config.rate_limit_delay)
            try:
                detail = await fetch_diary_detail(client, diary.id, diary.numero)
                details.append(detail)
            except Exception as exc:
                logger.error("Failed to fetch diary detail %s: %s", diary.id, exc)
    except Exception as exc:
        logger.error("Failed to process project '%s' (%s): %s", project_name, project_id, exc)
    return details


async def run_daily_report() -> None:
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz=tz)
    today = now.date()
    date_str = today.strftime("%d/%m/%Y")
    generated_at = now.strftime("%H:%M")

    logger.info("=== Daily report job started — %s ===", date_str)

    run = app_state.start_run()
    projects_count = 0
    diaries_count = 0

    try:
        async with httpx.AsyncClient(timeout=config.http_timeout) as client:
            try:
                all_projects = await fetch_all_projects(client)
            except Exception as exc:
                logger.error("Failed to fetch projects: %s", exc)
                app_state.finish_run(run, success=False, projects=0, diaries=0, error=str(exc))
                return

            active_projects = filter_active_projects(all_projects)
            if not active_projects:
                logger.warning("No active projects to process")
                app_state.finish_run(run, success=False, projects=0, diaries=0, error="Nenhum projeto ativo")
                return

            tasks = [
                _process_project(client, proj.id, proj.name, today)
                for proj in active_projects
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        all_diaries = [detail for project_details in results for detail in project_details]
        projects_count = len(active_projects)
        diaries_count = len(all_diaries)

        logger.info(
            "Processed %d project(s), found %d diary(ies) today",
            projects_count,
            diaries_count,
        )

        # Summarize comments with LLM (only for diaries that have comments)
        for diary in all_diaries:
            if diary.comentarios:
                diary.resumo_comentarios = await summarize_comments(
                    diary.comentarios,
                    diary.dados_projeto.nome,
                )

        report_data = ReportData(
            date_str=date_str,
            generated_at=generated_at,
            diaries=all_diaries,
        )
        message = build_report(report_data)

        success = await send_whatsapp_message(message)
        if success:
            logger.info("=== Daily report sent successfully ===")
        else:
            logger.error("=== Daily report FAILED to send ===")

        app_state.finish_run(
            run,
            success=success,
            projects=projects_count,
            diaries=diaries_count,
            error=None if success else "Falha ao enviar via WTS Chat",
        )

    except Exception as exc:
        logger.exception("Unexpected error in daily report job: %s", exc)
        app_state.finish_run(run, success=False, projects=projects_count, diaries=diaries_count, error=str(exc))


def run_daily_report_sync() -> None:
    asyncio.run(run_daily_report())
