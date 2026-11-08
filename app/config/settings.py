from __future__ import annotations

import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    bot_token: str = ""
    # NoDecode -> pydantic-settings не трогает JSON, отдаёт raw string в валидатор
    admin_ids: Annotated[list[int], NoDecode] = []
    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    env: str = "dev"
    log_level: str = "INFO"
    port: int = 10000
    check_interval_seconds: int = 600
    max_notifications_per_run: int = 20

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v: object) -> list[int]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            # поддержка обоих форматов: "1,2,3" и "[1,2,3]"
            if s.startswith("["):
                return [int(x) for x in json.loads(s)]
            return [int(x.strip()) for x in s.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        return []


settings = Settings()