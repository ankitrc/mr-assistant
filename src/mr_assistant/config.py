"""Settings read from environment variables / the .env file at the repo root."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_db: str = "mrchatbot"
    postgres_app_user: str = "mr_app"
    postgres_app_password: str

    pool_min_size: int = 1
    pool_max_size: int = 5

    @property
    def app_conninfo(self) -> str:
        """Connection string for the application role (row-level security applies)."""
        return (f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
                f"user={self.postgres_app_user} password={self.postgres_app_password}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
