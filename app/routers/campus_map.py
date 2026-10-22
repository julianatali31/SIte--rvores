"""Public campus map: planted trees (colored by watering badge) and planting zones."""
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.time import now_utc
from app.models import PlantingZone, Tree
from app.models.enums import TREE_STATUS_LABELS, DataReviewStatus
from app.services.storage import media_url
from app.services.tree_view import WATERABLE, badges_for

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
router = APIRouter()
SHORT_CACHE = {"Cache-Control": "no-store"}


@router.get("/mapa", include_in_schema=False)
async def map_page():
    return FileResponse(WEB_DIR / "map.html")


@router.get("/api/map/trees")
async def map_trees(session: AsyncSession = Depends(get_session)):
    """GeoJSON FeatureCollection with one point per planted tree. No internal notes."""
    trees = (
        await session.execute(
            select(Tree)
            .where(Tree.status.in_(WATERABLE), Tree.lat.is_not(None))
            .options(selectinload(Tree.species), selectinload(Tree.zone))
            .order_by(Tree.code)
        )
    ).scalars().all()
    badges = await badges_for(session, list(trees), now_utc())
    features = []
    for t in trees:
        badge = badges[t.id]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [t.lng, t.lat]},
                "properties": {
                    "public_id": t.public_id,
                    "code": t.code,
                    "common_name": t.species.common_name,
                    "scientific_name": t.species.scientific_name,
                    "species_reviewed": t.species.data_review_status == DataReviewStatus.REVIEWED,
                    "status": t.status,
                    "status_label": TREE_STATUS_LABELS[t.status],
                    "zone_name": t.zone.name if t.zone else None,
                    "badge_color": badge.color,
                    "badge_headline": badge.headline,
                    "badge_detail": badge.detail,
                    "photo_url": media_url(t.species.photo_path),
                    "url": f"/a/{t.public_id}",
                },
            }
        )
    return JSONResponse({"type": "FeatureCollection", "features": features}, headers=SHORT_CACHE)


@router.get("/api/map/zones")
async def map_zones(session: AsyncSession = Depends(get_session)):
    zones = (
        await session.execute(
            select(PlantingZone).where(PlantingZone.polygon_geojson.is_not(None)).order_by(PlantingZone.name)
        )
    ).scalars().all()
    return JSONResponse(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": z.polygon_geojson,
                    "properties": {"name": z.name, "description": z.description},
                }
                for z in zones
            ],
        },
        headers=SHORT_CACHE,
    )
