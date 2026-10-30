import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("CAREERPILOT_DATA_DIR", str(ROOT / "data")))
PRIVATE = DATA / "private"
OUTPUTS = DATA / "outputs"
for path in [PRIVATE, OUTPUTS]:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[ROOT / ".env", PRIVATE / ".env"], extra="ignore")
    database_url: str = f"sqlite:///{PRIVATE / 'careerpilot.db'}"
    api_token: str = Field(min_length=32)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    usajobs_api_key: str = ""
    usajobs_email: str = ""
    openai_api_key: str = ""


@lru_cache
def settings():
    return Settings()


@lru_cache
def engine():
    url = settings().database_url
    result = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(result, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return result


def database():
    with Session(engine()) as db:
        yield db
