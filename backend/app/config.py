from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root, one level above backend/
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    anthropic_api_key: str
    # Sent by the app as a Bearer token. Too short (or empty) = refuse to start.
    app_token: str = Field(min_length=32)
    food_model: str = "claude-opus-5-5"
    # SQLite DB + photos. Relative paths are resolved against the repo root.
    data_dir: Path = Path("data")
    # Defines what "today" means for the daily balance.
    timezone: str = "Europe/Stockholm"
    # Placeholder until the Strava provider exists.
    fixed_burned_kcal: int = 2500

    @field_validator("data_dir")
    @classmethod
    def _resolve_data_dir(cls, v: Path) -> Path:
        return v if v.is_absolute() else REPO_ROOT / v

    @property
    def db_path(self) -> Path:
        return self.data_dir / "calorie-balance.db"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"


settings = Settings()
