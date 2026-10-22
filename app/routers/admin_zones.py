from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_admin
from app.core.db import get_session
from app.models import PlantingZone
from app.routers.deps import commit_or_422, get_or_404
from app.schemas.admin import ZoneOut, ZonePatch
from app.services.geojson import GeoJSONError, extract_geometry

router = APIRouter(prefix="/api/admin/zones", tags=["admin"], dependencies=[Depends(current_admin)])


def _geometry_or_422(data: Any) -> dict[str, Any]:
    try:
        return extract_geometry(data)
    except GeoJSONError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from None


@router.get("", response_model=list[ZoneOut])
async def list_zones(session: AsyncSession = Depends(get_session)):
    return (await session.execute(select(PlantingZone).order_by(PlantingZone.name))).scalars().all()


@router.patch("/{zone_id}", response_model=ZoneOut)
async def update_zone(zone_id: int, body: ZonePatch, session: AsyncSession = Depends(get_session)):
    zone = await get_or_404(session, PlantingZone, zone_id, "Zona")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nome da zona é obrigatório.")
    if changes.get("polygon_geojson") is not None:
        changes["polygon_geojson"] = _geometry_or_422(changes["polygon_geojson"])
    for key, value in changes.items():
        setattr(zone, key, value)
    await commit_or_422(session)
    return zone


@router.put("/{zone_id}/geojson", response_model=ZoneOut)
async def import_geojson(
    zone_id: int, data: dict[str, Any] = Body(...), session: AsyncSession = Depends(get_session)
):
    """Import a GeoJSON geometry, Feature or single-feature FeatureCollection."""
    zone = await get_or_404(session, PlantingZone, zone_id, "Zona")
    zone.polygon_geojson = _geometry_or_422(data)
    await commit_or_422(session)
    return zone
