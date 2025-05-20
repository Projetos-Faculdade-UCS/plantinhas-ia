import os
from fastapi import HTTPException

def get_gemini_api_key() -> str:
    api_key = ""
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada")
    return api_key