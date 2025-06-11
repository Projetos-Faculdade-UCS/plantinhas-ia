import json
import re

import google.generativeai as genai
from fastapi import HTTPException
from google.generativeai import types

from schemas.models import EntradaPlantio, SaidaPlantio
from utils.helpers import get_gemini_api_key

SYSTEM_PROMPT = """
**Instruções ao modelo**
Você receberá um JSON de entrada com os campos: data_inicio_plantio (YYYY-MM-DD) e planta.dias_maturidade (número de dias).
**CALCULE** data_fim_plantio somando dias_maturidade a data_inicio_plantio, retornando no formato YYYY-MM-DD.
Gere descritivo_como_plantar adaptado às propriedades da planta.
Inclua informacoes_adicionais com recomendações extras.
Para tarefas, retorne um array de objetos com as chaves:
- nome (string)
- tipo (string — um dos: cultivo, irrigacao, nutricao, inspecao, poda, colheita)
- frequencia (string — um dos: semanal, diaria, mensal, trimestral, semestral, anual, unica)
- quantidade_total (inteiro)
- habilidade (objeto com nome e multiplicador_xp)
- opcionalmente tutorial (materiais + etapas)
**NÃO** inclua texto adicional fora do JSON. Use aspas duplas e mantenha a ordem das chaves: data_fim_plantio, descritivo_como_plantar, informacoes_adicionais, tarefas.
*SE* a temperatura_ideal for 0 ou não informada, você mesmo pega isso na sua base de dados.
*SE* o nome_cientifico não for válido, você mesmo corrige usando sua base de dados.
*ALERTA* Não retorne conteúdo ilegal, ofensivo ou impróprio. Se houver pedido de algo assim no JSON de entrada, retorne HTTP 400 com `"Erro: Solicitação inválida"`.
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
        response_mime_type="application/json",
    )

    try:
        response = model.generate_content(
            contents=input_json,
            generation_config=generation_config,
            safety_settings=safety_settings_list,
            stream=False
        )
        result_json = json.loads(response.text)

        for tarefa in result_json.get("tarefas", []):
            # normaliza quantidade_total
            qt = tarefa.get("quantidade_total")
            if isinstance(qt, str):
                m = re.search(r"(\d+)", qt)
                tarefa["quantidade_total"] = int(m.group(1)) if m else 0

            # converte cron em frequencia, se existir
            if "cron" in tarefa:
                tarefa["frequencia"] = tarefa.pop("cron")

            # normalize tutorial: materiais
            tut = tarefa.get("tutorial")
            if isinstance(tut, dict):
                # materiais: se vier lista de strings, converte
                mats = tut.get("materiais", [])
                normalized = []
                for item in mats:
                    if isinstance(item, str):
                        normalized.append({
                            "nome": item,
                            "quantidade": 1,
                            "unidade": "un"
                        })
                    else:
                        normalized.append(item)
                tut["materiais"] = normalized

                # etapas: se vier lista de strings, converte
                steps = tut.get("etapas", [])
                normalized_steps = []
                for idx, step in enumerate(steps, start=1):
                    if isinstance(step, str):
                        normalized_steps.append({
                            "descricao": step,
                            "ordem": idx
                        })
                    else:
                        normalized_steps.append(step)
                tut["etapas"] = normalized_steps

        return SaidaPlantio.parse_obj(result_json)

    except HTTPException:
        # repassa erros 400 solicitados
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar GeminAI: {e}")
