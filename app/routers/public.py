import re
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.ids import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH
from app.core.time import local_tz, now_utc
from app.models import CareEvent
from app.models.enums import CareEventType, EventSource
from app.schemas.public import TreeOut, WateringIn, WateringResult
from app.services.rate_limit import check_ip_rate_limit, hash_ip
from app.services.tree_view import WATERABLE, build_tree_out, last_watering_at, load_tree

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
_PUBLIC_ID_RE = re.compile(f"^[{PUBLIC_ID_ALPHABET}]{{{PUBLIC_ID_LENGTH}}}$")

router = APIRouter()
NO_STORE = {"Cache-Control": "no-store"}


def _valid_public_id(public_id: str) -> bool:
    return bool(_PUBLIC_ID_RE.match(public_id))


@router.get("/api/config")
async def public_config() -> dict:
    settings = get_settings()
    lat, lng = settings.map_center_latlng
    return {"map_center": {"lat": lat, "lng": lng}, "map_zoom": settings.map_zoom, "base_url": settings.base_url}


@router.get("/a/{public_id}", include_in_schema=False)
async def tree_page(public_id: str, session: AsyncSession = Depends(get_session)):
    found = _valid_public_id(public_id) and await load_tree(session, public_id) is not None
    return FileResponse(WEB_DIR / "tree.html", status_code=200 if found else 404)


@router.get("/api/trees/{public_id}", response_model=TreeOut)
async def get_tree(public_id: str, session: AsyncSession = Depends(get_session)):
    tree = await load_tree(session, public_id) if _valid_public_id(public_id) else None
    if tree is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Árvore não encontrada.")
    out = await build_tree_out(session, tree, now_utc())
    return JSONResponse(out.model_dump(mode="json"), headers=NO_STORE)


@router.post(
    "/api/trees/{public_id}/waterings",
    response_model=WateringResult,
    status_code=status.HTTP_201_CREATED,
    responses={404: {}, 409: {}, 429: {}},
)
async def register_watering(
    public_id: str,
    body: WateringIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    now = now_utc()
    tree = await load_tree(session, public_id) if _valid_public_id(public_id) else None
    if tree is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Árvore não encontrada.")

    # Honeypot: answer like a success, store nothing.
    if body.website:
        out = await build_tree_out(session, tree, now)
        return JSONResponse(
            WateringResult(message="Rega registrada. Obrigado!", tree=out).model_dump(mode="json"),
            status_code=status.HTTP_201_CREATED,
        )

    if tree.status not in WATERABLE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta árvore não está recebendo registros de rega.")

    ip_hash = hash_ip(request.client.host if request.client else None)
    limit = await check_ip_rate_limit(session, ip_hash, now)
    if not limit.allowed:
        return JSONResponse(
            {"detail": "Muitos registros em pouco tempo. Tente de novo mais tarde."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(limit.retry_after_seconds)},
        )

    tree = await load_tree(session, public_id, for_update=True)
    previous = await last_watering_at(session, tree.id)
    min_gap = timedelta(hours=settings.min_watering_interval_hours)
    if previous is not None and now - previous < min_gap:
        out = await build_tree_out(session, tree, now)
        await session.rollback()
        hhmm = previous.astimezone(local_tz()).strftime("%H:%M")
        return JSONResponse(
            {
                "detail": f"Esta árvore já foi regada às {hhmm}. Obrigado pelo cuidado!",
                "tree": out.model_dump(mode="json"),
            },
            status_code=status.HTTP_409_CONFLICT,
        )

    session.add(
        CareEvent(
            tree_id=tree.id,
            type=CareEventType.WATERING,
            performed_at=now,
            performed_by_name=body.name,
            source=EventSource.PUBLIC,
            ip_hash=ip_hash,
        )
    )
    await session.commit()
    out = await build_tree_out(session, tree, now)
    thanks = f"Obrigado, {body.name}! Rega registrada." if body.name else "Obrigado! Rega registrada."
    return JSONResponse(
        WateringResult(message=thanks, tree=out).model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
    )
