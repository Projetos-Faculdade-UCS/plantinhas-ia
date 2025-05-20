from pydantic import BaseModel, Field
from typing import List, Literal

class Planta(BaseModel):
    nome_cientifico: str
    solo_ideal: str
    ventilacao: str
    epoca_plantio: str
    temperatura_ideal: str
    dias_maturidade: int

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

class Tarefa(BaseModel):
    nome: str
    tipo: str
    quantidade_total: int
    cron: str
    habilidade: Habilidade

class SaidaPlantio(BaseModel):
    data_fim_plantio: str
    descritivo_como_plantar: str
    informacoes_adicionais: str
    tarefas: List[Tarefa]