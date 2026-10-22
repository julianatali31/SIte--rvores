from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CareEventType, DataReviewStatus, TreeStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


# --- auth ---------------------------------------------------------------------

class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


# --- species --------------------------------------------------------------------

class SpeciesIn(BaseModel):
    common_name: str = Field(min_length=1, max_length=120)
    scientific_name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    size_class: str | None = Field(default=None, max_length=60)
    root_notes: str | None = Field(default=None, max_length=2000)
    fruiting_season: str | None = Field(default=None, max_length=120)
    fun_fact: str | None = Field(default=None, max_length=2000)
    data_review_status: DataReviewStatus = DataReviewStatus.PENDING

    _clean = field_validator(
        "common_name", "scientific_name", "description", "size_class",
        "root_notes", "fruiting_season", "fun_fact", mode="before",
    )(_blank_to_none)


class SpeciesPatch(SpeciesIn):
    common_name: str | None = Field(default=None, min_length=1, max_length=120)
    data_review_status: DataReviewStatus | None = None


class SpeciesOut(ORM):
    id: int
    common_name: str
    scientific_name: str | None
    description: str | None
    size_class: str | None
    root_notes: str | None
    fruiting_season: str | None
    fun_fact: str | None
    photo_path: str | None
    data_review_status: DataReviewStatus
    tree_count: int = 0


# --- origins --------------------------------------------------------------------

class OriginIn(BaseModel):
    donor_name: str = Field(min_length=1, max_length=160)
    donated_at: date | None = None
    seedling_count: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)

    _clean = field_validator("donor_name", "notes", mode="before")(_blank_to_none)


class OriginPatch(OriginIn):
    donor_name: str | None = Field(default=None, min_length=1, max_length=160)


class OriginOut(ORM):
    id: int
    donor_name: str
    donated_at: date | None
    seedling_count: int | None
    notes: str | None


# --- zones ----------------------------------------------------------------------

class ZonePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    restrictions: str | None = Field(default=None, max_length=4000)
    polygon_geojson: dict[str, Any] | None = None

    _clean = field_validator("name", "description", "restrictions", mode="before")(_blank_to_none)


class ZoneOut(ORM):
    id: int
    name: str
    description: str | None
    restrictions: str | None
    polygon_geojson: dict[str, Any] | None


# --- trees ----------------------------------------------------------------------

class TreeCreate(BaseModel):
    species_id: int
    origin_id: int
    zone_id: int | None = None
    planting_batch: int | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=4000)


class TreePatch(BaseModel):
    species_id: int | None = None
    origin_id: int | None = None
    zone_id: int | None = None
    planting_batch: int | None = Field(default=None, gt=0)
    status: TreeStatus | None = None
    planted_at: datetime | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=4000)


class PlantIn(BaseModel):
    planted_at: datetime
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zone_id: int | None = None


class TreeOut(ORM):
    id: int
    code: str
    public_id: str
    species_id: int
    species_name: str
    origin_id: int
    zone_id: int | None
    zone_name: str | None
    planting_batch: int | None
    status: TreeStatus
    planted_at: datetime | None
    lat: float | None
    lng: float | None
    notes: str | None
    public_url: str
    badge_color: str | None = None
    badge_headline: str | None = None


class PhotoOut(ORM):
    id: int
    url: str
    taken_at: datetime
    caption: str | None


class CareEventIn(BaseModel):
    type: CareEventType
    performed_at: datetime | None = None
    performed_by_name: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=280)

    _clean = field_validator("performed_by_name", "notes", mode="before")(_blank_to_none)


class CareEventOut(ORM):
    id: int
    type: CareEventType
    performed_at: datetime
    performed_by_name: str | None
    notes: str | None
    source: str


# --- rain & rules --------------------------------------------------------------

class RainIn(BaseModel):
    occurred_at: datetime | None = None
    precipitation_mm: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=1)
    notes: str | None = Field(default=None, max_length=280)

    _clean = field_validator("notes", mode="before")(_blank_to_none)


class RainOut(ORM):
    id: int
    occurred_at: datetime
    precipitation_mm: Decimal | None
    source: str
    notes: str | None


class WateringRulePatch(BaseModel):
    interval_days: float | None = Field(default=None, gt=0, le=365)
    phase_until_days: int | None = Field(default=None, gt=0, le=3650)
    is_placeholder: bool | None = None
    note: str | None = Field(default=None, max_length=280)


class WateringRuleOut(ORM):
    id: int
    phase: str
    interval_days: float
    phase_until_days: int | None
    is_placeholder: bool
    note: str | None
