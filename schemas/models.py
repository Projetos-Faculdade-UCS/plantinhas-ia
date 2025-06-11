from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class TemperaturaIdeal(BaseModel):
    minima: int
    maxima: int
    ideal: int


class Dificuldade(BaseModel):
    value: float
    label: str


class Planta(BaseModel):
    nome: str
    nome_cientifico: str
    dificuldade: Dificuldade
    temperatura_ideal: TemperaturaIdeal


class Ambiente(BaseModel):
    local: str
    condicao: Literal['interno', 'externo']


class EntradaPlantio(BaseModel):
    data_inicio_plantio: str = Field(..., pattern=r"\d{4}-\d{2}-\d{2}")
    planta: Planta
    quantidade: int
    ambiente: Ambiente
    sistemaCultivo: str
    informacoes_adicionais: str
    habilidades_existentes: List[str]


class Habilidade(BaseModel):
    nome: str
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
    tipo: Literal['cultivo', 'irrigacao', 'nutricao', 'inspecao', 'poda', 'colheita']
    frequencia: Literal['semanal', 'diaria', 'mensal', 'trimestral', 'semestral', 'anual', 'unica']
    quantidade_total: int
    habilidade: Habilidade
    tutorial: Optional[Tutorial] = None


class SaidaPlantio(BaseModel):
    data_fim_plantio: str
    descritivo_como_plantar: str
    informacoes_adicionais: str
    tarefas: List[Tarefa]
