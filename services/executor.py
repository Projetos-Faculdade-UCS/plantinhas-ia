import json
import re

import google.generativeai as genai
from fastapi import HTTPException
from google.generativeai import types

from schemas.models import EntradaPlantio, SaidaPlantio
from utils.helpers import get_gemini_api_key

SYSTEM_PROMPT = """
**Instruções ao modelo**
Você receberá um JSON contendo informações de uma planta, as condições de plantio e as habilidades do usuário.
Sua tarefa é gerar um JSON de saída com as informações necessárias para o cadastro de um plantio.

Gere o JSON com as seguintes chaves:

- data_fim_plantio: somando planta.dias_maturidade com data_inicio_plantio, retornando no formato YYYY-MM-DD.
- informacoes_adicionais: recomendações gerais de como plantar. Coloque informações específicas
para ambiente e sistemaCultivo, informados no JSON de entrada. Recomendo você escrever de duas a três frases.
- tarefas: retorne um array de objetos. Uma tarefa deve ter:
  - nome: string
  - tipo: string (cultivo, irrigacao, nutricao, inspecao, poda, colheita)
  - cron: string com um crontab com quea tarefadeve ser executada
  - quantidade_total: inteiro representa quantas vezes a tarefa deve ser executada
    - Para tarefas com uma alta frequência, como irrigação, use um numero alto.
    - Use 1 para tarefas que devem ser executadas apenas uma vez.
  - habilidade: objeto com as chaves nome e nivel:
    - id: string (id da habilidade)
    - multiplicador_xp: float (multiplicador de XP para a habilidade)
      - use 1.2 para que a tarefa gere 20% a mais de XP por execução
    - Use como base as habilidades fornecidas no JSON de entrada
  - tutorial: lista de objetos com as chaves:
    - materiais: objeto com as chaves:
      - nome: string (nome do material)
      - quantidade: float (quantidade necessária)
      - unidade: string (unidade de medida do material)
    - etapas: lista de objetos com as chaves:
      - ordem: inteiro (ordem da etapa)
      - descricao: string (descrição da etapa)
Exemplo de saída:

```json
{
  "data_fim_plantio": "2023-10-30",
  "informacoes_adicionais": "Plante em solo bem drenado e com boa exposição solar.",
  "tarefas": [
    {
      "nome": "Plantar",
      "tipo": "cultivo",
      "cron": "0 8 * * *",
      "quantidade_total": 1,
      "habilidade": {
        "id": "preparacao_solo",
        "multiplicador_xp": 1.4
      },
      "tutorial": {
        "materiais": [
          {
            "nome": "pá comum",
            "quantidade": 1,
            "unidade": "unidade"
          },
          {
            "nome": "composto orgânico",
            "quantidade": 5,
            "unidade": "kg"
          }
        ],
        "etapas": [
          {
            "ordem": 1,
            "descricao": "Remover pedras e detritos do solo."
          },
          {
            "ordem": 2,
            "descricao": "Aflorar o solo com a pá."
          },
          {
            "ordem": 3,
            "descricao": "Adicionar composto orgânico."
          }
        ]
      }
    }
  ]
}
```
---------------------
- **NÃO** inclua texto adicional fora do JSON.
- Use aspas duplas e mantenha a ordem das chaves: data_fim_plantio, informacoes_adicionais, tarefas.
- **ALERTA** Não retorne conteúdo ilegal, ofensivo ou impróprio. Se houver pedido de algo assim no JSON de entrada, retorne HTTP 400 com `"Erro: Solicitação inválida"`
- Gere uma tarefa para cada tipo (cultivo, irrigacao, nutricao, inspecao, poda, colheita) que seja relevante para a planta e as condições de plantio.;
  - Não gere tarefas com tipos iguais;
  - Caso a planta não precise de uma tarefa, não gere-a
    - Exemplo: se a planta não precisa de poda, não gere uma tarefa de poda.
  - Não gere tarefa de inspecao a menos que solicitado explicitamente.
  - Tipos obrigatórios: cultivo, irrigacao, nutricao.
"""


def transformar_com_geminai(entrada: EntradaPlantio) -> SaidaPlantio:
    api_key = get_gemini_api_key()
    genai.configure(api_key=api_key)
    model_name = "gemini-2.0-flash"

    model = genai.GenerativeModel(
        model_name=model_name, system_instruction=SYSTEM_PROMPT
    )

    input_json = json.dumps(entrada.dict(), ensure_ascii=False)

    safety_settings_list = [
        {
            "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        },
        {
            "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        },
        {
            "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        },
        {
            "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            "threshold": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
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
            stream=False,
        )
        result_json = json.loads(response.text)

        for tarefa in result_json.get("tarefas", []):
            # normaliza quantidade_total
            qt = tarefa.get("quantidade_total")
            if isinstance(qt, str):
                m = re.search(r"(\d+)", qt)
                tarefa["quantidade_total"] = int(m.group(1)) if m else 0

            # normalize tutorial: materiais
            tut = tarefa.get("tutorial")
            if isinstance(tut, dict):
                # materiais: se vier lista de strings, converte
                mats = tut.get("materiais", [])
                normalized = []
                for item in mats:
                    if isinstance(item, str):
                        normalized.append(
                            {"nome": item, "quantidade": 1, "unidade": "un"}
                        )
                    else:
                        normalized.append(item)
                tut["materiais"] = normalized

                # etapas: se vier lista de strings, converte
                steps = tut.get("etapas", [])
                normalized_steps = []
                for idx, step in enumerate(steps, start=1):
                    if isinstance(step, str):
                        normalized_steps.append({"descricao": step, "ordem": idx})
                    else:
                        normalized_steps.append(step)
                tut["etapas"] = normalized_steps

        return SaidaPlantio.parse_obj(result_json)

    except HTTPException:
        # repassa erros 400 solicitados
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar GeminAI: {e}")
