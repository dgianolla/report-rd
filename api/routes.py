import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from api.state import app_state
from config import config

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Response models ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    uptime_since: Optional[str] = None


class RunSummary(BaseModel):
    started_at: str
    finished_at: Optional[str]
    success: Optional[bool]
    projects_processed: int
    diaries_found: int
    error: Optional[str]


class StatusResponse(BaseModel):
    service: str = "rd-obras-whatsapp-report"
    scheduler_running: bool
    job_running: bool
    next_run_at: Optional[str]
    schedule: str
    timezone: str
    total_runs: int
    total_sent: int
    total_failed: int
    last_run: Optional[RunSummary]


class TriggerResponse(BaseModel):
    message: str
    triggered_at: str


class StatsResponse(BaseModel):
    total_runs: int
    total_sent: int
    total_failed: int
    history: list[RunSummary]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else None


def _run_summary(run) -> RunSummary:
    return RunSummary(
        started_at=run.started_at.strftime("%d/%m/%Y %H:%M:%S"),
        finished_at=_fmt(run.finished_at),
        success=run.success,
        projects_processed=run.projects_processed,
        diaries_found=run.diaries_found,
        error=run.error,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["Monitoramento"])
def health():
    """Verifica se o serviço está no ar."""
    return HealthResponse(status="ok")


@router.get("/status", response_model=StatusResponse, tags=["Monitoramento"])
def status():
    """
    Retorna o estado completo do serviço:
    - Se o scheduler está rodando
    - Se um job está em execução agora
    - Próximo envio agendado
    - Totais de envios com sucesso/falha
    - Último job executado
    """
    next_run = app_state.next_run_at()
    scheduler_ok = app_state.scheduler is not None and app_state.scheduler.running

    return StatusResponse(
        scheduler_running=scheduler_ok,
        job_running=app_state.job_running,
        next_run_at=_fmt(next_run),
        schedule=f"Diariamente às {config.report_hour:02d}:{config.report_minute:02d}",
        timezone=config.timezone,
        total_runs=len(app_state.runs),
        total_sent=app_state.total_sent,
        total_failed=app_state.total_failed,
        last_run=_run_summary(app_state.last_run) if app_state.last_run else None,
    )


@router.post("/report/trigger", response_model=TriggerResponse, tags=["Relatório"])
async def trigger_report(background_tasks: BackgroundTasks):
    """
    Dispara o relatório diário **imediatamente**, sem esperar o horário agendado.
    Roda em background — retorna imediatamente enquanto o job executa.
    """
    if app_state.job_running:
        raise HTTPException(status_code=409, detail="Um relatório já está em execução. Aguarde o término.")

    from jobs.daily_report import run_daily_report
    background_tasks.add_task(asyncio.run, run_daily_report())

    return TriggerResponse(
        message="Relatório disparado com sucesso. Acompanhe em /status.",
        triggered_at=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )


@router.get("/report/stats", response_model=StatsResponse, tags=["Relatório"])
def report_stats():
    """
    Histórico completo de todas as execuções do relatório nesta sessão.
    Inclui data/hora, projetos processados, diários encontrados e status.
    """
    return StatsResponse(
        total_runs=len(app_state.runs),
        total_sent=app_state.total_sent,
        total_failed=app_state.total_failed,
        history=[_run_summary(r) for r in reversed(app_state.runs)],
    )
