"""
Unit tests for report_builder, filters, date handling, and climate/status mappings.
Run with: python -m pytest test_report.py -v
"""
import sys
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

# ── Fixtures ──────────────────────────────────────────────────────────────────

from models.schemas import (
    DiaryDetail, Period, ProjectData, Employee, EmployeeData,
    EmployeeRole, ActionPlanData, ReportData, Project, DiaryEntry,
)
from services.report_builder import build_report, _clima, _status, CLIMA_MAP, STATUS_MAP
from services.rd_obras import filter_active_projects
from services.wts_chat import _split_message


def make_employee(nome="JOÃO SILVA", cargo="OPERÁRIO", trabalhou="yes", folga="no", horas=8.0):
    return Employee(
        dados=EmployeeData(nome=nome, cargo=EmployeeRole(nome=cargo)),
        trabalhou=trabalhou,
        folga=folga,
        horas_normais=horas,
    )


def make_diary(
    nome_projeto="PROJETO TESTE",
    status="filling",
    clima_manha="sunny",
    clima_tarde="cloudy",
    clima_noite="rainy",
    funcionarios=None,
    equipes=None,
    numero=1,
) -> DiaryDetail:
    return DiaryDetail(
        id="abc123",
        numero_diario=numero,
        dados_projeto=ProjectData(
            nome=nome_projeto,
            endereco="RUA TESTE",
            numero="100",
            bairro="CENTRO",
            cidade="SOROCABA (SP)",
        ),
        manha=Period(habilitado="yes", clima=clima_manha),
        tarde=Period(habilitado="yes", clima=clima_tarde),
        noite=Period(habilitado="no", clima=clima_noite),
        status=status,
        funcionarios=funcionarios or [make_employee()],
        dados_plano_acao=ActionPlanData(
            descricao="RELATÓRIO DIÁRIO",
            equipes=equipes or ["EQUIPE OPERACIONAL"],
        ),
    )


# ── Climate mapping tests ─────────────────────────────────────────────────────

class TestClimaMapping:
    def test_sunny(self):
        assert _clima("sunny") == "☀️ Ensolarado"

    def test_cloudy(self):
        assert _clima("cloudy") == "☁️ Nublado"

    def test_rainy(self):
        assert _clima("rainy") == "🌧️ Chuvoso"

    def test_stormy(self):
        assert _clima("stormy") == "⛈️ Tempestade"

    def test_unknown_passthrough(self):
        assert _clima("windy") == "windy"

    def test_empty_string(self):
        assert _clima("") == "N/A"

    def test_none_via_empty(self):
        # _clima receives strings; empty maps to N/A
        assert _clima("N/A") == "N/A"


# ── Status mapping tests ──────────────────────────────────────────────────────

class TestStatusMapping:
    def test_filling(self):
        assert _status("filling") == "📝 Em preenchimento"

    def test_approved(self):
        assert _status("approved") == "✅ Aprovado"

    def test_disabled(self):
        assert _status("disabled") == "❌ Desabilitado"

    def test_unknown(self):
        assert _status("draft") == "draft"


# ── Project filter tests ──────────────────────────────────────────────────────

class TestProjectFilter:
    def _make_projects(self):
        return [
            Project(id="1", name="ESCRITÓRIO"),
            Project(id="2", name="L' ESSENCE CAMPOLIM | PINTURA PREDIAL"),
            Project(id="3", name="GM | MANUTENÇÃO EM TELHADO"),
            Project(id="4", name="escritório filial"),  # case insensitive
        ]

    def test_removes_ignored(self):
        projects = self._make_projects()
        active = filter_active_projects(projects)
        names = [p.name for p in active]
        assert "ESCRITÓRIO" not in names
        assert "escritório filial" not in names

    def test_keeps_active(self):
        projects = self._make_projects()
        active = filter_active_projects(projects)
        assert len(active) == 2

    def test_empty_list(self):
        assert filter_active_projects([]) == []


# ── Diary date filter test ────────────────────────────────────────────────────

class TestDiaryDateFilter:
    def _parse_date(self, raw: str) -> date:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()

    def test_today_match(self):
        raw = "2026-03-14T00:00:00.000Z"
        parsed = self._parse_date(raw)
        assert parsed == date(2026, 3, 14)

    def test_yesterday_no_match(self):
        raw = "2026-03-13T23:59:59.000Z"
        parsed = self._parse_date(raw)
        assert parsed != date(2026, 3, 14)

    def test_utc_vs_brt(self):
        # UTC midnight = BRT -3h = previous day in BRT
        raw = "2026-03-14T00:00:00.000Z"
        utc_date = self._parse_date(raw)
        # The service compares diary UTC date with BRT today; this test shows raw parsing
        assert utc_date == date(2026, 3, 14)


# ── Report builder tests ──────────────────────────────────────────────────────

class TestReportBuilder:
    def test_empty_diaries_message(self):
        report = ReportData(date_str="14/03/2026", generated_at="18:00", diaries=[])
        msg = build_report(report)
        assert "Nenhum diário" in msg
        assert "14/03/2026" in msg

    def test_single_project_report(self):
        diary = make_diary(nome_projeto="ALPHA PROJECT", status="approved")
        report = ReportData(date_str="14/03/2026", generated_at="18:00", diaries=[diary])
        msg = build_report(report)
        assert "ALPHA PROJECT" in msg
        assert "✅ Aprovado" in msg
        assert "☀️ Ensolarado" in msg
        assert "JOÃO SILVA" in msg
        assert "OPERÁRIO" in msg
        assert "8h trabalhadas" in msg
        assert "EQUIPE OPERACIONAL" in msg

    def test_multiple_projects_sorted_alphabetically(self):
        diary_z = make_diary(nome_projeto="ZETA CORP")
        diary_a = make_diary(nome_projeto="ALPHA INC")
        report = ReportData(date_str="14/03/2026", generated_at="18:00", diaries=[diary_z, diary_a])
        msg = build_report(report)
        pos_a = msg.index("ALPHA INC")
        pos_z = msg.index("ZETA CORP")
        assert pos_a < pos_z

    def test_absent_employees_listed(self):
        employees = [
            make_employee("PRESENTE SILVA", trabalhou="yes", folga="no"),
            make_employee("AUSENTE JONES", trabalhou="no", folga="no"),
            make_employee("FOLGA MARIA", trabalhou="yes", folga="yes"),
        ]
        diary = make_diary(funcionarios=employees)
        report = ReportData(date_str="14/03/2026", generated_at="18:00", diaries=[diary])
        msg = build_report(report)
        assert "AUSENTE JONES" in msg
        assert "FOLGA MARIA" in msg
        assert "ausente" in msg or "folga" in msg

    def test_summary_counts(self):
        employees = [make_employee(horas=8), make_employee("OUTRO", horas=4)]
        diary = make_diary(funcionarios=employees)
        report = ReportData(date_str="14/03/2026", generated_at="18:00", diaries=[diary])
        msg = build_report(report)
        assert "12h" in msg  # 8 + 4
        assert "Projetos com atividade hoje: 1" in msg
        assert "Total de funcionários em campo: 2" in msg

    def test_header_present(self):
        report = ReportData(date_str="14/03/2026", generated_at="18:00", diaries=[make_diary()])
        msg = build_report(report)
        assert "RELATÓRIO DIÁRIO DE OBRA" in msg
        assert "14/03/2026" in msg
        assert "18:00" in msg


# ── Message splitting tests ───────────────────────────────────────────────────

class TestMessageSplitting:
    def test_short_message_not_split(self):
        text = "Hello world"
        chunks = _split_message(text, max_chars=100)
        assert chunks == ["Hello world"]

    def test_long_message_split(self):
        text = "A" * 200
        chunks = _split_message(text, max_chars=100)
        assert len(chunks) >= 2

    def test_split_labels_added(self):
        text = "A" * 200
        chunks = _split_message(text, max_chars=100)
        assert "Parte 1/" in chunks[0]
        assert "Parte 2/" in chunks[1]

    def test_exact_limit_not_split(self):
        text = "B" * 60
        chunks = _split_message(text, max_chars=60)
        assert len(chunks) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
