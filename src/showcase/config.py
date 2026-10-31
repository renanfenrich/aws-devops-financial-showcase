import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    api_token: str

    @classmethod
    def from_env(cls) -> Settings:
        database_url = os.environ.get("DATABASE_URL", "")
        api_token = os.environ.get("API_TOKEN", "")
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URI")
        if len(api_token) < 32:
            raise ValueError("API_TOKEN must contain at least 32 characters")
        return cls(database_url, api_token)
