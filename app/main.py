from fastapi import FastAPI

app = FastAPI(title="Plantando Ideias — Árvores do Campus")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
