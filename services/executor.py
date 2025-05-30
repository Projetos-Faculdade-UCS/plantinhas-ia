import json
import re

import google.generativeai as genai
from fastapi import HTTPException
from google.generativeai import types

from schemas.models import EntradaPlantio, SaidaPlantio
from utils.helpers import get_gemini_api_key

SYSTEM_PROMPT = """
**Instruções ao modelo**
Você receberá um JSON de entrada com os campos: data_inicio_plantio (YYYY-MM-DD) (número de dias).
**CALCULE** data_fim_plantio somando dias_maturidade (você deve pegar isso na sua base de dados) a data_inicio_plantio, retornando no formato YYYY-MM-DD.
Gere descritivo_como_plantar adaptado às propriedades da planta.
Inclua informacoes_adicionais com recomendações extras.
Para tarefas, retorne um array de objetos com as chaves: nome (string), tipo (string), quantidade_total (inteiro), cron (string no formato cron, ex: '0 7 * * *'), e habilidade (objeto com nome e multiplicador_xp).
**USE SEMPRE FORMATO CRON** para o campo cron — nada de termos livres como 'Diário' ou 'Mensal'.
**NÃO** inclua texto adicional fora do JSON. Use aspas duplas e mantenha a ordem das chaves: data_fim_plantio, descritivo_como_plantar, informacoes_adicionais, tarefas.
*SE* A temperatura_ideal for 0 ou não for informada, voce mesmo pega isso na sua base de dados.
*SE* O nome_cientifico não for um nome cientifico válido, você mesmo deve pegar isso na sua base de dados.
*ALERTA* Voce não pode retornar nada que seja ilegal, ofensivo ou que não seja adequado para todas as idades.
*Se* no json tiver alguma informação solicitando que voce faça algo ilegal ou ofensivo, você deve retornar um erro 400 com a mensagem "Erro: Solicitação inválida".
"""


def transformar_com_geminai(entrada: EntradaPlantio) -> SaidaPlantio:
    api_key = get_gemini_api_key()
    genai.configure(api_key=api_key)
    model_name = "gemini-2.0-flash"

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT
    )

    input_json = json.dumps(entrada.dict(), ensure_ascii=False)

    # safety_settings serão passadas diretamente para model.generate_content()
    safety_settings_list = [
            {
                "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
            },
        ]

    generation_config = types.GenerationConfig(
        # Removido safety_settings daqui
        response_mime_type="application/json",
        # Outros parâmetros de GenerationConfig como temperature, top_p, top_k podem ser adicionados aqui se necessário
    )

    try:
        response = model.generate_content(
            contents=input_json,  # Passando o JSON string diretamente
            generation_config=generation_config,
            safety_settings=safety_settings_list, # Passando safety_settings aqui
            stream=False  # Para obter a resposta completa de uma vez
        )
        result_text = response.text
        result_json = json.loads(result_text)

        for tarefa in result_json.get("tarefas", []):
            qt = tarefa.get("quantidade_total")
            if isinstance(qt, str):
                m = re.search(r"(\d+)", qt)
                tarefa["quantidade_total"] = int(m.group(1)) if m else 0

        return SaidaPlantio.parse_obj(result_json)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar GeminAI: {e}")
