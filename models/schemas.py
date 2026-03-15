from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Project:
    id: str
    name: str


@dataclass
class DiaryEntry:
    id: str
    numero: int
    data: str
    status: str


@dataclass
class EmployeeRole:
    nome: str = "N/A"


@dataclass
class EmployeeData:
    nome: str = "N/A"
    cargo: EmployeeRole = field(default_factory=EmployeeRole)


@dataclass
class Employee:
    dados: EmployeeData = field(default_factory=EmployeeData)
    trabalhou: str = "no"
    folga: str = "no"
    horas_normais: float = 0.0


@dataclass
class Period:
    habilitado: str = "no"
    clima: str = "N/A"


@dataclass
class ProjectData:
    nome: str = "N/A"
    endereco: str = "N/A"
    numero: str = "N/A"
    bairro: str = "N/A"
    cidade: str = "N/A"


@dataclass
class ActionPlanData:
    descricao: str = "N/A"
    equipes: list[str] = field(default_factory=list)


@dataclass
class CreatedBy:
    nome_usuario: str = "N/A"
    data: str = "N/A"


@dataclass
class DiaryDetail:
    id: str
    numero_diario: int
    dados_projeto: ProjectData
    manha: Period
    tarde: Period
    noite: Period
    status: str
    funcionarios: list[Employee]
    dados_plano_acao: ActionPlanData
    comentarios: list[str] = field(default_factory=list)
    resumo_comentarios: Optional[str] = None
    periodo_trabalho: str = "daytime"
    feriado: str = "no"
    criado_em: Optional[CreatedBy] = None


@dataclass
class ReportData:
    date_str: str
    generated_at: str
    diaries: list[DiaryDetail] = field(default_factory=list)
