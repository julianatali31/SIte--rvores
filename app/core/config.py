from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-me"


def normalize_database_url(url: str) -> str:
    """Accepts the URLs Neon/Vercel hand out and makes them asyncpg-compatible.

    postgres:// or postgresql:// -> postgresql+asyncpg://, sslmode -> ssl,
    and drops libpq-only options asyncpg rejects (channel_binding).
    """
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "sslmode":
            key = "ssl"
        if key == "channel_binding":
            continue
        query.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/arvores"

    # Set by Vercel itself (VERCEL=1, VERCEL_ENV=production|preview|development).
    vercel: bool = False
    vercel_env: str | None = None
    # Present when a Vercel Blob store is linked: photos go to Blob instead of local disk.
    blob_read_write_token: str | None = None

    # Permanent public URL printed on the QR plaques. Never change after printing.
    base_url: str = "http://localhost:8000"

    # "lat,lng" of the campus, used to center maps.
    map_center: str = "-28.2620,-52.4060"
    map_zoom: int = 18

    timezone: str = "America/Sao_Paulo"

    secret_key: str = Field(default=DEV_SECRET, min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    ip_hash_salt: str = Field(default=DEV_SECRET, min_length=16)

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

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self):
        if self.is_production:
            weak = [n for n in ("secret_key", "ip_hash_salt") if getattr(self, n) == DEV_SECRET]
            if weak:
                raise ValueError(f"Defina {', '.join(n.upper() for n in weak)} em produção.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production" or self.vercel_env == "production"

    @property
    def serverless(self) -> bool:
        """On Vercel each request may run in a fresh instance: no connection pool."""
        return self.vercel

    @property
    def storage_backend(self) -> str:
        return "blob" if self.blob_read_write_token else "local"

    @property
    def map_center_latlng(self) -> tuple[float, float]:
        lat, lng = (float(p) for p in self.map_center.split(","))
        return lat, lng


@lru_cache
def get_settings() -> Settings:
    return Settings()
