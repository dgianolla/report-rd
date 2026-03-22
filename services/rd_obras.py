import asyncio
import logging
import re
from datetime import date, timezone, datetime
from html.parser import HTMLParser

import httpx

from config import config
from models.schemas import (
    Project, DiaryEntry, DiaryDetail, Period,
    ProjectData, Employee, EmployeeData, EmployeeRole,
    ActionPlanData, CreatedBy
)

logger = logging.getLogger(__name__)

RETRY_DELAYS = [2, 4, 8]
_PENDENCIA_RE = re.compile(r"pend[eê]ncia", re.IGNORECASE)


class _HTMLStripper(HTMLParser):
    """Extrai texto puro de HTML, convertendo <br>/<li>/<p> em quebras de linha."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ARG002
        if tag in ("br", "p", "li"):
            self._parts.append("\n")

    def get_text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self._parts)).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


def _extract_pendencias(texto: str) -> list[str]:
    """Retorna frases/linhas que mencionam pendência."""
    pendencias = []
    for line in texto.splitlines():
        line = line.strip()
        if line and _PENDENCIA_RE.search(line):
            pendencias.append(line)
    return pendencias


def _rd_headers() -> dict:
    return {
        "x-app-key": config.rd_obras_app_key,
        "x-app-secret": config.rd_obras_app_secret,
        "Content-Type": "application/json",
    }


async def _post_with_retry(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    last_exc = None
    for attempt, delay in enumerate([0] + RETRY_DELAYS, start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            resp = await client.post(url, json=payload, headers=_rd_headers())
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            logger.warning("Attempt %d/%d failed for %s: %s", attempt, len(RETRY_DELAYS) + 1, url, exc)
    raise last_exc


async def fetch_all_projects(client: httpx.AsyncClient) -> list[Project]:
    url = f"{config.rd_obras_base_url}/projetos"
    page = 1
    projects: list[Project] = []

    while True:
        data = await _post_with_retry(client, url, {"pagina": page, "registros_por_pagina": 100})
        for rec in data.get("registros", []):
            projects.append(Project(id=rec["_id"], name=rec.get("name", "")))

        if page >= data.get("total_de_paginas", 1):
            break
        page += 1
        await asyncio.sleep(config.rate_limit_delay)

    logger.info("Fetched %d total projects", len(projects))
    return projects


def filter_active_projects(projects: list[Project]) -> list[Project]:
    ignored = config.ignored_projects
    active = [
        p for p in projects
        if not any(ign in p.name.upper() for ign in ignored)
    ]
    logger.info("Active projects after filter: %d (ignored %d)", len(active), len(projects) - len(active))
    return active


async def fetch_today_diaries(client: httpx.AsyncClient, project_id: str, today: date) -> list[DiaryEntry]:
    url = f"{config.rd_obras_base_url}/diarios"
    page = 1
    today_diaries: list[DiaryEntry] = []

    while True:
        data = await _post_with_retry(client, url, {
            "projeto": project_id,
            "pagina": page,
            "registros_por_pagina": 50,
        })
        records = data.get("registros", [])

        for rec in records:
            status = rec.get("status", "")
            if status == "disabled":
                continue
            raw_date = rec.get("data", "")
            try:
                diary_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
            except (ValueError, AttributeError):
                continue
            if diary_date == today:
                today_diaries.append(DiaryEntry(
                    id=rec["idDiario"],
                    numero=rec.get("numero", 0),
                    data=raw_date,
                    status=status,
                ))

        # Diaries are ordered newest first; stop when all records in page are older than today
        if records and today_diaries:
            # We have found today's diaries; check if the last record is from today or before
            last_raw = records[-1].get("data", "")
            try:
                last_date = datetime.fromisoformat(last_raw.replace("Z", "+00:00")).date()
                if last_date < today:
                    break
            except (ValueError, AttributeError):
                pass

        if page >= data.get("total_de_paginas", 1):
            break

        # Only go to next page if no records yet or first page was today only
        if not any(
            datetime.fromisoformat(r.get("data", "").replace("Z", "+00:00")).date() >= today
            for r in records
            if r.get("data")
        ):
            break

        page += 1
        await asyncio.sleep(config.rate_limit_delay)

    return today_diaries


def _parse_period(raw: dict | None) -> Period:
    if not raw:
        return Period()
    return Period(
        habilitado=raw.get("habilitado", "no") or "no",
        clima=raw.get("clima", "N/A") or "N/A",
    )


def _parse_employee(raw: dict) -> Employee:
    func_data = raw.get("dadosFuncionario", {}) or {}
    cargo_data = func_data.get("dadosCargo", {}) or {}
    return Employee(
        dados=EmployeeData(
            nome=func_data.get("nome", "N/A") or "N/A",
            cargo=EmployeeRole(nome=cargo_data.get("nome", "N/A") or "N/A"),
        ),
        trabalhou=raw.get("trabalhou", "no") or "no",
        folga=raw.get("folga", "no") or "no",
        horas_normais=float(raw.get("horasNormais", 0) or 0),
    )


def _parse_project_data(raw: dict | None) -> ProjectData:
    if not raw:
        return ProjectData()
    return ProjectData(
        nome=raw.get("nome", "N/A") or "N/A",
        endereco=raw.get("endereco", "N/A") or "N/A",
        numero=raw.get("numero", "N/A") or "N/A",
        bairro=raw.get("bairro", "N/A") or "N/A",
        cidade=raw.get("cidade", "N/A") or "N/A",
    )


def _parse_action_plan(raw: dict | None) -> ActionPlanData:
    if not raw:
        return ActionPlanData()
    equipes = [e.get("nome", "") for e in raw.get("listaEquipes", []) if e.get("nome")]
    return ActionPlanData(
        descricao=raw.get("descricao", "N/A") or "N/A",
        equipes=equipes,
    )


def _parse_created_by(raw: dict | None) -> CreatedBy | None:
    if not raw:
        return None
    user_data = raw.get("dadosUsuario", {}) or {}
    return CreatedBy(
        nome_usuario=user_data.get("nome", "N/A") or "N/A",
        data=raw.get("data", "N/A") or "N/A",
    )


async def fetch_diary_detail(client: httpx.AsyncClient, diary_id: str, numero: int) -> DiaryDetail:
    url = f"{config.rd_obras_base_url}/diarios/json"
    data = await _post_with_retry(client, url, {"idDiario": diary_id})

    raw_comentarios = data.get("comentarios") or []
    comentarios = [
        c.get("texto") or c.get("descricao") or str(c)
        for c in raw_comentarios
        if isinstance(c, dict) and (c.get("texto") or c.get("descricao"))
    ]

    ocorrencias_texto: list[str] = []
    pendencias: list[str] = []
    for oc in data.get("ocorrencias") or []:
        html = oc.get("descricao") or ""
        if not html:
            continue
        texto = _strip_html(html)
        if texto:
            ocorrencias_texto.append(texto)
            pendencias.extend(_extract_pendencias(texto))

    return DiaryDetail(
        id=diary_id,
        numero_diario=numero,
        dados_projeto=_parse_project_data(data.get("dadosProjeto")),
        manha=_parse_period(data.get("manha")),
        tarde=_parse_period(data.get("tarde")),
        noite=_parse_period(data.get("noite")),
        status=data.get("status", "filling") or "filling",
        funcionarios=[_parse_employee(e) for e in data.get("funcionarios", [])],
        dados_plano_acao=_parse_action_plan(data.get("dadosPlanoAcao")),
        comentarios=comentarios,
        ocorrencias_texto=ocorrencias_texto,
        pendencias=pendencias,
        periodo_trabalho=data.get("periodoTrabalho", "daytime") or "daytime",
        feriado=data.get("feriado", "no") or "no",
        criado_em=_parse_created_by(data.get("criadoEm")),
    )
