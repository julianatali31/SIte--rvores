"""Campus rain records and watering rules."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import current_admin
from app.core.db import get_session
from app.core.time import assume_local, now_utc
from app.models import RainEvent, User, WateringRule
from app.models.enums import RainSource
from app.routers.deps import commit_or_422, get_or_404
from app.schemas.admin import RainIn, RainOut, WateringRuleOut, WateringRulePatch

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_admin)])


@router.get("/rain-events", response_model=list[RainOut])
async def list_rain(session: AsyncSession = Depends(get_session)):
    rows = await session.execute(select(RainEvent).order_by(RainEvent.occurred_at.desc()).limit(100))
    return rows.scalars().all()


@router.post("/rain-events", response_model=RainOut, status_code=status.HTTP_201_CREATED)
async def add_rain(
    body: RainIn, session: AsyncSession = Depends(get_session), user: User = Depends(current_admin)
):
    when = assume_local(body.occurred_at) if body.occurred_at else now_utc()
    if when > now_utc():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A data da chuva não pode estar no futuro.")
    rain = RainEvent(
        occurred_at=when,
        precipitation_mm=body.precipitation_mm,
        notes=body.notes,
        source=RainSource.MANUAL,
        created_by_id=user.id,
    )
    session.add(rain)
    await commit_or_422(session)
    return rain


@router.delete("/rain-events/{rain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rain(rain_id: int, session: AsyncSession = Depends(get_session)):
    rain = await get_or_404(session, RainEvent, rain_id, "Registro de chuva")
    await session.delete(rain)
    await commit_or_422(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/watering-rules", response_model=list[WateringRuleOut])
async def list_rules(session: AsyncSession = Depends(get_session)):
    return (await session.execute(select(WateringRule).order_by(WateringRule.id))).scalars().all()


@router.patch("/watering-rules/{rule_id}", response_model=WateringRuleOut)
async def update_rule(rule_id: int, body: WateringRulePatch, session: AsyncSession = Depends(get_session)):
    rule = await get_or_404(session, WateringRule, rule_id, "Regra")
    changes = body.model_dump(exclude_unset=True)
    if "interval_days" in changes and changes["interval_days"] is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Intervalo é obrigatório.")
    if changes.get("is_placeholder") is None:
        changes.pop("is_placeholder", None)
    for key, value in changes.items():
        setattr(rule, key, value)
    await commit_or_422(session)
    return rule
