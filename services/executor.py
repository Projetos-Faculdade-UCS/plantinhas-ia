import json
import re
from fastapi import HTTPException
from google import genai
from google.genai import types
from schemas.models import EntradaPlantio, SaidaPlantio
from utils.helpers import get_gemini_api_key

SYSTEM_PROMPT = """
**Instruções ao modelo**
Você receberá um JSON de entrada com os campos: data_inicio_plantio (YYYY-MM-DD) e planta.dias_maturidade (número de dias).
**CALCULE** data_fim_plantio somando dias_maturidade a data_inicio_plantio, retornando no formato YYYY-MM-DD.
Gere descritivo_como_plantar adaptado às propriedades da planta.
Inclua informacoes_adicionais com recomendações extras.
Para tarefas, retorne um array de objetos com as chaves: nome (string), tipo (string), quantidade_total (inteiro), cron (string no formato cron, ex: '0 7 * * *'), e habilidade (objeto com nome e multiplicador_xp).
**USE SEMPRE FORMATO CRON** para o campo cron — nada de termos livres como 'Diário' ou 'Mensal'.
**NÃO** inclua texto adicional fora do JSON. Use aspas duplas e mantenha a ordem das chaves: data_fim_plantio, descritivo_como_plantar, informacoes_adicionais, tarefas.
**SE** O dias_maturidade for igual a 0 calcule voce mesmo os dias de maturidade baseado na planta.
*SE* A temperatura_ideal for 0 ou não for informada, voce mesmo pega isso na sua base de dados.
*SE* O nome_cientifico não for um nome cientifico válido, você mesmo deve pegar isso na sua base de dados.
*ALERTA* Voce não pode retornar nada que seja ilegal, ofensivo ou que não seja adequado para todas as idades.
*Se* no json tiver alguma informação solicitando que voce faça algo ilegal ou ofensivo, você deve retornar um erro 400 com a mensagem "Erro: Solicitação inválida".
"""

def transformar_com_geminai(entrada: EntradaPlantio) -> SaidaPlantio:
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)
    model = "gemini-2.0-flash"

    input_json = json.dumps(entrada.dict(), ensure_ascii=False)
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=input_json)],
        ),
    ]

    generate_config = types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_LOW_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_LOW_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_LOW_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_LOW_AND_ABOVE"),
        ],
        response_mime_type="application/json",
        system_instruction=[types.Part.from_text(text=SYSTEM_PROMPT)],
    )

    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_config,
        )
        result_text = ''.join(chunk.text for chunk in stream)
        result_json = json.loads(result_text)

        for tarefa in result_json.get('tarefas', []):
            qt = tarefa.get('quantidade_total')
            if isinstance(qt, str):
                m = re.search(r"(\d+)", qt)
                tarefa['quantidade_total'] = int(m.group(1)) if m else 0

        return SaidaPlantio.parse_obj(result_json)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar GeminAI: {e}")