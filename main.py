from fastapi import FastAPI
from routers.processador import router as processador_router

app = FastAPI()

app.include_router(processador_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)