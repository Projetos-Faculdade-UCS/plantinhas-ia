import json
import re

import google.generativeai as genai
from fastapi import HTTPException
from google.generativeai import types

from schemas.models import EntradaPlantio, SaidaPlantio
from utils.helpers import get_gemini_api_key

SYSTEM_PROMPT = """
You will receive a JSON containing:
- `plant`: details about a plant species
- `planting_conditions`: details about the environment and cultivation method
- `user_skills`: user's current skill levels related to planting
- `additional_info`: additional information about the planting process

---

## 🎯 Your task

Return a **single JSON** containing:
1. `data_fim_plantio`: Estimated planting end date
2. `informacoes_adicionais`: Brazilian Portuguese tips for planting that plant in the given conditions
3. `tarefas`: List of tasks needed for the planting process

---

## 📌 Output structure

### 1. `data_fim_plantio`
- Add `plant.days_to_maturity` to `planting_conditions.start_date`
- Format as `YYYY-MM-DD`

---

### 2. `informacoes_adicionais`
- Write **2 to 3 sentences in Brazilian Portuguese**
- Focus on:
  - The plant’s specific needs
  - The provided environment (`planting_conditions.environment`)
  - The cultivation system (`planting_conditions.cultivation_system`)
  - The aditional information provided (`planting_conditions.additional_info`)

---

### 3. `tarefas` (Array of task objects)

Generate 1 task per **relevant** `tipo`, from the list:

| tipo         | Required? | When to include                 |
|--------------|-----------|---------------------------------|
| cultivo      | ✅ Yes    | Always                          |
| irrigacao    | ✅ Yes    | Always                          |
| nutricao     | ✅ Yes    | Always                          |
| poda         | Optional  | Only if the plant requires it   |
| colheita     | Optional  | Only if applicable              |
| inspecao     | Optional  | Only if explicitly requested    |

Each task must include:

```json
{
  "nome": "string",
  "tipo": "cultivo | irrigacao | nutricao | poda | colheita | inspecao",
  "cron": "use one of the valid cron expressions listed below",
  "quantidade_total": integer,
  "habilidade": {
    "id": "string (from user_skills)",
    "multiplicador_xp": float (e.g. 1.2 for +20% XP)
  },
  "tutorial": {
    "materiais": [
      {
        "nome": "string",
        "quantidade": float,
        "unidade": "string"
      }
    ],
    "etapas": [
      {
        "ordem": integer,
        "descricao": "string"
      }
    ]
  }
}
```

---

## ⏰ Cron Expression Rules

You **must only use one of the following cron patterns**:

| Frequência        | Cron Expression       | When to use                           |
|-------------------|-----------------------|----------------------------------------|
| Diariamente       | `0 8 * * *`           | For daily tasks like irrigation        |
| Semanalmente      | `0 8 * * 1`           | For weekly routines like nutrition     |
| Mensalmente       | `0 8 1 * *`           | For monthly maintenance (e.g. poda)    |
| Anualmente        | `0 8 1 1 *`           | For harvest or long-term cycles        |
| A cada N meses    | `0 8 1 */N *`         | For medium-term planning               |
| A cada N dias     | `0 8 */N * *`         | For mid-to-high-frequency events       |

---

## ⚠️ Error Handling

Return this if the input is invalid or off-topic:

### 🔴 If request contains **illegal, offensive, or inappropriate content**:
```json
{ "Erro": "Solicitação inválida" }
```

### 🟠 If the input is **unrelated to planting** (e.g. animal care, home automation, recipes, etc):
```json
{ "Erro": "Conteúdo fora do escopo da aplicação de plantio" }
```

### 🟡 If the input is **too vague** or lacks required fields:
```json
{ "Erro": "Dados insuficientes para gerar tarefas de plantio" }
```

---

## 🔄 Output Language

✅ **All output must be written in Brazilian Portuguese**
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
