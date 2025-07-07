from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Dificuldade(BaseModel):
    value: float
    label: str


class Planta(BaseModel):
    nome: str
    nome_cientifico: str
    dificuldade: Dificuldade
    dias_maturidade: int
    temperatura_minima: str
    temperatura_maxima: str
    temperatura_ideal: str


class Ambiente(BaseModel):
    local: str
    condicao: Literal["interno", "externo"]


class Habilidade(BaseModel):
    id: int
    nome: str
    descricao: Optional[str] = None


class EntradaPlantio(BaseModel):
    data_inicio_plantio: str = Field(..., pattern=r"\d{4}-\d{2}-\d{2}")
    planta: Planta
    quantidade: int
    ambiente: str
    sistemaCultivo: str
    informacoes_adicionais: str
    habilidades_existentes: List[Habilidade]


class HabilidadeTarefa(BaseModel):
    id: str
    multiplicador_xp: float


class Material(BaseModel):
    nome: str
    quantidade: float
    unidade: str


class Etapa(BaseModel):
    descricao: str
    ordem: int


class Tutorial(BaseModel):
    materiais: List[Material]
    etapas: List[Etapa]


class Tarefa(BaseModel):
    nome: str
    tipo: Literal["cultivo", "irrigacao", "nutricao", "inspecao", "poda", "colheita"]
    cron: str
    quantidade_total: int
    habilidade: HabilidadeTarefa
    tutorial: Optional[Tutorial] = None


class SaidaPlantio(BaseModel):
    data_fim_plantio: str
    informacoes_adicionais: str
    tarefas: List[Tarefa]
