"""
Shared in-memory state between the scheduler and the FastAPI app.
All fields are updated by jobs/daily_report.py at runtime.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler


@dataclass
class ReportRun:
    started_at: datetime
    finished_at: Optional[datetime] = None
    success: Optional[bool] = None
    projects_processed: int = 0
    diaries_found: int = 0
    error: Optional[str] = None


class AppState:
    def __init__(self):
        self.scheduler: Optional["BackgroundScheduler"] = None
        self.job_running: bool = False
        self.runs: list[ReportRun] = []

    # ── Helpers ──────────────────────────────────────────────────────────────

    def start_run(self) -> ReportRun:
        run = ReportRun(started_at=datetime.now())
        self.runs.append(run)
        self.job_running = True
        return run

    def finish_run(self, run: ReportRun, success: bool, projects: int, diaries: int, error: str | None = None):
        run.finished_at = datetime.now()
        run.success = success
        run.projects_processed = projects
        run.diaries_found = diaries
        run.error = error
        self.job_running = False

    @property
    def total_sent(self) -> int:
        return sum(1 for r in self.runs if r.success)

    @property
    def total_failed(self) -> int:
        return sum(1 for r in self.runs if r.success is False)

    @property
    def last_run(self) -> Optional[ReportRun]:
        return self.runs[-1] if self.runs else None

    def next_run_at(self) -> Optional[datetime]:
        if not self.scheduler:
            return None
        job = self.scheduler.get_job("daily_report")
        if not job:
            return None
        return job.next_run_time


# Singleton — imported everywhere
app_state = AppState()
