"""
backend/app/core/settings.py
Pydantic Settings for SatQuery AI.
All configuration is read from environment variables (or .env file in development).
Missing required variables produce a clear, immediate error on startup.
"""

from __future__ import annotations

import json
from pathlib import Path

# Resolve .env relative to this file so it works regardless of CWD.
# settings.py → app/core/ → app/ → backend/ → workspace root (d:\final sih)
_THIS_FILE = Path(__file__).resolve()
_BACKEND_DIR = _THIS_FILE.parent.parent.parent          # d:\final sih\backend
_WORKSPACE_ROOT = _BACKEND_DIR.parent                  # d:\final sih
_ENV_FILE_PATH = _WORKSPACE_ROOT / ".env"              # d:\final sih\.env
# Fall back to backend/.env (Docker / CI) if workspace root .env absent
if not _ENV_FILE_PATH.exists():
    _ENV_FILE_PATH = _BACKEND_DIR / ".env"
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    In development, Pydantic reads from a .env file automatically.
    In production, set env vars in Docker Compose / Kubernetes / etc.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def assemble_defaults(cls, data: Any) -> Any:
        """
        Assemble composite URLs from component fields when the full URL is absent.
        Does NOT read os.environ directly — pydantic-settings already loads env vars
        into `data` before this validator runs. Direct os.environ reads would bypass
        test isolation via monkeypatch and break the missing-required-var tests.
        """
        if isinstance(data, dict):
            # Auto-assemble database_url from component fields if absent
            if not data.get("database_url"):
                user = data.get("postgres_user") or "postgres"
                pwd = data.get("postgres_password", "")
                db = data.get("postgres_db") or "satquery"
                if pwd:
                    import urllib.parse
                    encoded_pwd = urllib.parse.quote_plus(str(pwd).strip())
                    data["database_url"] = f"postgresql+asyncpg://{user}:{encoded_pwd}@localhost:5432/{db}"
                else:
                    data["database_url"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/satquery"
            # Auto-assemble redis_url if absent
            if not data.get("redis_url"):
                data["redis_url"] = "redis://localhost:6379/0"
        return data

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_env: Literal["development", "production"] = "development"
    data_mode: Literal["online", "test"] = "online"

    # -------------------------------------------------------------------------
    # Authentication (single-operator; ADR-012)
    # -------------------------------------------------------------------------
    operator_username: str = Field(
        default="admin",
        description="Single-operator username",
    )
    operator_password: str = Field(
        ...,
        description="Single-operator password",
    )
    secret_key: str = Field(
        ...,
        min_length=32,
        description="Session/CSRF secret key",
        validation_alias=AliasChoices("secret_key", "SECRET_KEY"),
    )

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/satquery",
        description="Async SQLAlchemy database URL",
    )
    postgres_user: str = "postgres"
    postgres_password: str = Field(
        default="postgres",
        description="PostgreSQL password",
    )
    postgres_db: str = "satquery"

    # -------------------------------------------------------------------------
    # Redis & Celery
    # -------------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for pub/sub and cache",
    )
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    allowed_origins: list[str] | str = Field(
        default=["http://localhost:5173"],
        description="Comma-separated list or JSON array of allowed CORS origins",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            val = v.strip()
            if val.startswith("[") and val.endswith("]"):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(o).strip() for o in parsed if str(o).strip()]
                except Exception:
                    pass
            return [o.strip() for o in val.split(",") if o.strip()]
        if isinstance(v, list):
            return [str(o).strip() for o in v if str(o).strip()]
        return [str(v)]

    # -------------------------------------------------------------------------
    # Groq (optional)
    # -------------------------------------------------------------------------
    groq_api_key: str | None = None
    groq_model: str = "llama3-8b-8192"

    @property
    def groq_available(self) -> bool:
        return bool(self.groq_api_key)

    # -------------------------------------------------------------------------
    # Copernicus Data Space (ADR-009)
    # -------------------------------------------------------------------------
    copernicus_client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("copernicus_client_id", "client_id"),
    )
    copernicus_client_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("copernicus_client_secret", "client_secret"),
    )
    copernicus_token_url: str = (
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE"
        "/protocol/openid-connect/token"
    )
    copernicus_stac_url: str = "https://catalogue.dataspace.copernicus.eu/stac"
    copernicus_odata_url: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"

    @property
    def copernicus_available(self) -> bool:
        return bool(self.copernicus_client_id and self.copernicus_client_secret)

    # -------------------------------------------------------------------------
    # MapTiler — public key exposed via VITE_ prefix; no private key in frontend
    # -------------------------------------------------------------------------
    vite_maptiler_api_key: str | None = Field(
        default=None,
        description="Public, origin-restricted MapTiler key (browser-visible by design)",
        validation_alias=AliasChoices("vite_maptiler_api_key", "maptiler_api_key"),
    )

    # -------------------------------------------------------------------------
    # HuggingFace
    # -------------------------------------------------------------------------
    huggingface_token: str | None = None

    # -------------------------------------------------------------------------
    # ML Models
    # -------------------------------------------------------------------------
    remoteclip_model_path: str = "./models/remoteclip/RemoteCLIP-ViT-L-14.pt"
    remoteclip_sha256: str | None = None
    remoteclip_embedding_dim: int = 768

    changeformer_checkpoint_path: str = "./models/changeformer/ChangeFormerV6.pth"
    changeformer_sha256: str | None = "a4b97cc372734c554fd5deac61ff5639741ee038ef63c3f3a556a91872f2c742"
    changeformer_training_dataset: str = "LEVIR-CD"


    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------
    device: Literal["cuda", "cpu"] = "cpu"
    batch_size: int = Field(8, ge=1, le=128)
    worker_concurrency: int = Field(1, ge=1)
    cpu_threads: int = Field(4, ge=1)

    # -------------------------------------------------------------------------
    # Storage paths
    # -------------------------------------------------------------------------
    data_path: str = "./data"
    cache_path: str = "./data/cache"
    index_path: str = "./indexes"
    report_path: str = "./reports"
    free_disk_reserve_gb: float = Field(5.0, ge=0.5)
    storage_budget_gb: float = Field(50.0, ge=1.0)

    # -------------------------------------------------------------------------
    # Tile / grid settings
    # -------------------------------------------------------------------------
    tile_size: int = Field(256, ge=64, le=1024)
    top_k: int = Field(20, ge=1, le=500)
    max_results: int = Field(100, ge=1, le=1000)

    # -------------------------------------------------------------------------
    # Change detection thresholds (ADR-006 — explicit units)
    # These are unevaluated engineering defaults, NOT detection guarantees.
    # -------------------------------------------------------------------------
    change_threshold: float = Field(0.55, ge=0.0, le=1.0)
    min_change_area_m2: float = Field(
        900.0,
        ge=0.0,
        description="Minimum change polygon area in square metres. "
        "At 10 m grid: 1 pixel = 100 m². Default = 9 px × 100 m². "
        "Unevaluated engineering default.",
    )
    min_change_pixels: int = Field(
        9,
        ge=1,
        description="Minimum connected-component pixel count. "
        "Effective minimum = max(min_change_pixels × pixel_area_m2, min_change_area_m2).",
    )

    # -------------------------------------------------------------------------
    # QC / confidence scoring (ADR-013)
    # -------------------------------------------------------------------------
    qc_weights_version: str = "v1.0"
    confidence_weights: dict[str, float] = Field(
        default={
            "valid_ratio": 0.20,
            "registration_quality": 0.20,
            "cloud_quality": 0.15,
            "season_similarity": 0.15,
            "temporal_consistency": 0.20,
            "model_score": 0.10,
        },
        description="Confidence factor weights. Missing factors contribute 0 weight.",
    )

    @field_validator("confidence_weights", mode="before")
    @classmethod
    def parse_weights(cls, v: str | dict) -> dict:
        if isinstance(v, str):
            return json.loads(v)
        return v

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "Settings":
        total = sum(self.confidence_weights.values())
        if total > 1.0 + 1e-6:
            raise ValueError(
                f"confidence_weights sum {total:.4f} > 1.0; "
                "adjust weights so they sum to ≤ 1.0"
            )
        return self

    # -------------------------------------------------------------------------
    # AOI and job limits
    # -------------------------------------------------------------------------
    max_aoi_area_km2: float = Field(10_000.0, ge=0.01)
    max_aoi_vertices: int = Field(1000, ge=3)
    max_date_span_days: int = Field(3650, ge=1)
    max_scenes_per_job: int = Field(50, ge=1)
    max_raster_pixels_per_job: int = Field(1_000_000_000, ge=1)
    max_upload_bytes: int = Field(52_428_800, ge=1)        # 50 MB
    max_decoded_image_pixels: int = Field(268_435_456, ge=1)  # 256 MP

    # -------------------------------------------------------------------------
    # Timeouts and retries
    # -------------------------------------------------------------------------
    request_timeout_s: float = Field(30.0, ge=1.0)
    retry_limit: int = Field(3, ge=0)
    retry_backoff_s: float = Field(2.0, ge=0.1)
    job_time_limit_s: int = Field(3600, ge=60)
    event_retention_days: int = Field(30, ge=1)

    # -------------------------------------------------------------------------
    # Production guards
    # -------------------------------------------------------------------------
    @model_validator(mode="after")
    def production_guards(self) -> "Settings":
        if self.app_env == "production":
            if self.operator_password in ("changeme_strong_password", "password", ""):
                raise ValueError("Insecure OPERATOR_PASSWORD in production")
            if len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY too short for production")
        return self


# Singleton instance — import this everywhere
settings = Settings()  # type: ignore[call-arg]
