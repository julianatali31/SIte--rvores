from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import public

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

TILE_HOSTS = "https://*.tile.openstreetmap.org https://server.arcgisonline.com"
CSP = (
    "default-src 'self'; "
    f"img-src 'self' data: blob: {TILE_HOSTS}; "
    "script-src 'self'; style-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)

app = FastAPI(title="Plantando Ideias — Árvores do Campus")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith(("/docs", "/redoc")):  # Swagger UI loads from a CDN
        response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(public.router)

upload_dir = Path(get_settings().upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=upload_dir), name="media")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
