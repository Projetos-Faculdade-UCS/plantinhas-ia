import os

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()


def get_gemini_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY não configurada")
    return api_key
