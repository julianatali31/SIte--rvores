import re
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class WateringIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    # Honeypot: hidden from people, bots tend to fill it.
    website: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = " ".join(_CONTROL.sub(" ", v).split())
        if len(v) > 60:
            raise ValueError("Nome muito longo (máximo 60 caracteres).")
        return v or None


class SpeciesOut(BaseModel):
    common_name: str
    scientific_name: str | None
    description: str | None
    size_class: str | None
    root_notes: str | None
    fruiting_season: str | None
    fun_fact: str | None
    photo_url: str | None
    data_review_status: str


class OriginOut(BaseModel):
    donor_name: str
    donated_at: date | None


class LocationOut(BaseModel):
    lat: float
    lng: float


class BadgeOut(BaseModel):
    color: str
    headline: str  # "Regada há 2 dias" / "Choveu há 1 dia" / "Sem registro de rega"
    detail: str | None  # "ontem, 08:10"
    hint: str  # what a passer-by should do
    last_water_at: datetime | None
    last_water_source: str | None  # "watering" | "rain"
    due_at: datetime | None
    due_text: str | None  # "Próxima rega até sex 23/10" / "Rega atrasada desde qua 21/10"
    last_watering_at: datetime | None
    last_watering_text: str | None
    recent_rain: bool
    interval_days: float
    rule_is_placeholder: bool


class WateringOut(BaseModel):
    performed_at: datetime
    who: str
    when_text: str


class PhotoOut(BaseModel):
    url: str
    taken_at: datetime
    taken_label: str
    caption: str | None


class TreeOut(BaseModel):
    public_id: str
    code: str
    status: str
    status_label: str
    species: SpeciesOut
    origin: OriginOut
    zone_name: str | None
    planted_at: datetime | None
    age_text: str | None
    location: LocationOut | None
    badge: BadgeOut | None
    can_water: bool
    min_watering_interval_hours: float
    recent_waterings: list[WateringOut]
    photos: list[PhotoOut]
    map_center: LocationOut


class WateringResult(BaseModel):
    message: str
    tree: TreeOut
