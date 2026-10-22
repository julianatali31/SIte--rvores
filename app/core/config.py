from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/arvores"

    # Permanent public URL printed on the QR plaques. Never change after printing.
    base_url: str = "http://localhost:8000"

    # "lat,lng" of the campus, used to center maps.
    map_center: str = "-28.2620,-52.4060"
    map_zoom: int = 18

    timezone: str = "America/Sao_Paulo"

    secret_key: str = Field(default="dev-only-change-me", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    ip_hash_salt: str = Field(default="dev-only-change-me", min_length=16)
    trust_proxy_headers: bool = False

    min_watering_interval_hours: float = 3.0
    watering_rate_limit_count: int = 10
    watering_rate_limit_window_minutes: int = 60
    badge_warn_ratio: float = Field(default=0.75, gt=0, lt=1)

    upload_dir: str = "./uploads"
    max_upload_mb: int = 10

    admin_username: str | None = None
    admin_password: str | None = None

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def map_center_latlng(self) -> tuple[float, float]:
        lat, lng = (float(p) for p in self.map_center.split(","))
        return lat, lng


@lru_cache
def get_settings() -> Settings:
    return Settings()
