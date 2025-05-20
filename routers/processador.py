from fastapi import APIRouter
from schemas.models import EntradaPlantio, SaidaPlantio
from services.executor import transformar_com_geminai

router = APIRouter()

@router.post("/", response_model=SaidaPlantio)
async def gerar(entrada: EntradaPlantio):
    return transformar_com_geminai(entrada)