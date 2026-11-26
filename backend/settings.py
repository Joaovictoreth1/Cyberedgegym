from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    environment: Literal["development", "test", "production"] = "development"
    database_url: Path = Path("cyberedge.db")
    allowed_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    admin_token: SecretStr | None = None
    contact_rate_limit: Annotated[int, Field(ge=1, le=1000)] = 10
    contact_rate_window_seconds: Annotated[int, Field(ge=1, le=3600)] = 60
    contact_rate_max_clients: Annotated[int, Field(ge=1, le=100_000)] = 10_000
    max_request_bytes: Annotated[int, Field(ge=1024, le=65_536)] = 4096

    @property
    def origins(self) -> list[str]:
        return list(
            dict.fromkeys(part.strip() for part in self.allowed_origins.split(",") if part.strip())
        )

    @field_validator("database_url", mode="before")
    @classmethod
    def persistent_sqlite_path(cls, value: str | Path) -> str | Path:
        raw = str(value)
        if not raw.strip() or raw == ":memory:" or raw.startswith("file:") or "://" in raw:
            raise ValueError("use um caminho de arquivo SQLite")
        return value

    @field_validator("admin_token", mode="before")
    @classmethod
    def optional_admin_token(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_deployment(self) -> "Settings":
        for origin in self.origins:
            url = urlsplit(origin)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username is not None
                or url.path
                or url.query
                or url.fragment
                or origin != f"{url.scheme}://{url.netloc}"
                or any(char.isspace() or char in "*\\" for char in origin)
                or url.port == 0
            ):
                raise ValueError(
                    "ALLOWED_ORIGINS deve conter origens HTTP(S) explícitas, sem barra final"
                )
            if self.environment == "production" and url.scheme != "https":
                raise ValueError("origens de produção devem usar HTTPS")
        if self.admin_token is not None:
            token = self.admin_token.get_secret_value()
            if (
                len(token) < 32
                or not token.isascii()
                or any(not 33 <= ord(c) <= 126 for c in token)
            ):
                raise ValueError("ADMIN_TOKEN deve ter pelo menos 32 caracteres ASCII sem espaços")
        elif self.environment == "production":
            raise ValueError("ADMIN_TOKEN é obrigatório em produção")
        return self
