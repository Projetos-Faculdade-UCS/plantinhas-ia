import os
import json
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import List, Literal
from google import genai
from google.genai import types

app = FastAPI()

# ----------------------------
# MODELOS
# ----------------------------

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

# ----------------------------
# TRANSFORMAÇÃO COM GEMINAI
# ----------------------------

def transformar_com_geminai(entrada: EntradaPlantio) -> SaidaPlantio:
    """
    Executa chamada ao modelo Gemini via google-genai para transformar
    o JSON de entrada em JSON de saída conforme especificação.
    Apenas o GeminAI define todos os campos, sem fallback.
    Normaliza 'quantidade_total' para inteiro extraindo dígitos.
    """
    api_key = ""
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada")

    client = genai.Client(api_key=api_key)
    model = "gemini-2.0-flash"

    input_json = json.dumps(entrada.dict(), ensure_ascii=False)
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=input_json)],
        ),
    ]

    system_prompt = """
**Instruções ao modelo**
Você receberá um JSON de entrada com os campos: data_inicio_plantio (YYYY-MM-DD) e planta.dias_maturidade (número de dias).
**CALCULE** data_fim_plantio somando dias_maturidade a data_inicio_plantio, retornando no formato YYYY-MM-DD.
Gere descritivo_como_plantar adaptado às propriedades da planta.
Inclua informacoes_adicionais com recomendações extras.
Para tarefas, retorne um array de objetos com as chaves: nome (string), tipo (string), quantidade_total (inteiro), cron (string no formato cron, ex: '0 7 * * *'), e habilidade (objeto com nome e multiplicador_xp).
**USE SEMPRE FORMATO CRON** para o campo cron — nada de termos livres como 'Diário' ou 'Mensal'. Exemplos: diário '0 7 * * *'; quinzenal '0 9 */15 * *'; colheita '0 8 {dia} {mes} *'.
**NÃO** inclua texto adicional fora do JSON. Use aspas duplas e mantenha a ordem das chaves: data_fim_plantio, descritivo_como_plantar, informacoes_adicionais, tarefas.
**NÃO** inclua chaves extras ou texto fora do JSON. Use aspas duplas e mantenha a ordem das chaves: data_fim_plantio, descritivo_como_plantar, informacoes_adicionais, tarefas
**CASO**    "dias_maturidade": "0" faça o calculo voce mesmo de quanto tempo em dias leva para a planta crescer.
"""

    generate_config = types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_LOW_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_LOW_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_LOW_AND_ABOVE"),
        ],
        response_mime_type="application/json",
        system_instruction=[types.Part.from_text(text=system_prompt)],
    )

    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_config,
        )
        result_text = ''.join(chunk.text for chunk in stream)
        result_json = json.loads(result_text)

        # Normaliza quantidade_total para inteiro
        for tarefa in result_json.get('tarefas', []):
            qt = tarefa.get('quantidade_total')
            if isinstance(qt, str):
                m = re.search(r"(\d+)", qt)
                tarefa['quantidade_total'] = int(m.group(1)) if m else 0

        return SaidaPlantio.parse_obj(result_json)

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar GeminAI: {e}")

# ----------------------------
# ENDPOINT
# ----------------------------

@app.post("/", response_model=SaidaPlantio)
def gerar(entrada: EntradaPlantio):
    return transformar_com_geminai(entrada)

# ----------------------------
# RODAR COM UVICORN
# ----------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
