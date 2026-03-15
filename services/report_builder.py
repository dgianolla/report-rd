from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import config
from models.schemas import DiaryDetail, Period, ReportData

CLIMA_MAP: dict[str, str] = {
    "sunny": "☀️",
    "light": "🌤️",
    "cloudy": "☁️",
    "rainy": "🌧️",
    "stormy": "⛈️",
}

STATUS_MAP: dict[str, str] = {
    "filling": "📝 Em preenchimento",
    "approved": "✅ Aprovado",
    "disabled": "❌ Desabilitado",
}


def _clima(value: str) -> str:
    return CLIMA_MAP.get(value, value or "N/A")


def _status(value: str) -> str:
    return STATUS_MAP.get(value, value or "N/A")


def _format_period(label: str, period: Period) -> str:
    if period.habilitado == "no":
        return f"   {label}: — (desabilitado)"
    return f"   {label}: {_clima(period.clima)}"


def _format_diary(diary: DiaryDetail) -> str:
    proj = diary.dados_projeto
    address = f"{proj.endereco}, {proj.numero} - {proj.bairro}, {proj.cidade}"

    present = [e for e in diary.funcionarios if e.trabalhou == "yes"]
    absent = [e for e in diary.funcionarios if e.trabalhou == "no"]

    total = len(diary.funcionarios)
    present_count = len(present)

    ocorrencia = diary.dados_plano_acao.descricao
    lines = [
        f"🏗️ *{proj.nome}*",
        f"📍 {address}",
        f"📊 Status: {_status(diary.status)}",
        f"📝 Diário Nº: {diary.numero_diario}",
    ]

    if ocorrencia and ocorrencia != "N/A":
        lines += ["", f"📌 *Ocorrência:* {ocorrencia}"]

    lines += [
        "",
        "🌤️ *Clima:*",
        _format_period("Manhã", diary.manha),
        _format_period("Tarde", diary.tarde),
        _format_period("Noite", diary.noite),
    ]

    lines += ["", f"👷 *Funcionários presentes ({present_count}/{total}):*"]
    if present:
        for emp in present:
            lines.append(
                f"   • {emp.dados.nome} — {emp.dados.cargo.nome}"
            )
    else:
        lines.append("   Nenhum funcionário presente")

    if absent:
        lines += ["", "🚫 *Ausentes:*"]
        for emp in absent:
            lines.append(f"   • {emp.dados.nome} — {emp.dados.cargo.nome}")

    if diary.resumo_comentarios:
        lines += ["", f"💬 *Comentários:* {diary.resumo_comentarios}"]

    if diary.dados_plano_acao.equipes:
        lines += ["", "🏢 *Equipes:*"]
        for eq in diary.dados_plano_acao.equipes:
            lines.append(f"   • {eq}")

    return "\n".join(lines)


def build_report(report_data: ReportData) -> str:
    diaries = sorted(report_data.diaries, key=lambda d: d.dados_projeto.nome)

    header = (
        "📋 *RELATÓRIO DIÁRIO DE OBRA*\n"
        f"📅 Data: {report_data.date_str}\n"
        f"🕐 Gerado às: {report_data.generated_at}"
    )

    if not diaries:
        return (
            f"📋 Relatório Diário — {report_data.date_str}: "
            "Nenhum diário de obra registrado para hoje."
        )

    sep = "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    diary_blocks = sep.join(_format_diary(d) for d in diaries)

    total_present = sum(
        len([e for e in d.funcionarios if e.trabalhou == "yes"])
        for d in diaries
    )
    total_hours = sum(
        e.horas_normais
        for d in diaries
        for e in d.funcionarios
        if e.trabalhou == "yes"
    )

    summary = (
        "📊 *RESUMO GERAL:*\n"
        f"   🏗️ Projetos com atividade hoje: {len(diaries)}\n"
        f"   👷 Total de funcionários em campo: {total_present}"
    )

    return "\n".join([
        header,
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
        diary_blocks,
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
        summary,
    ])
