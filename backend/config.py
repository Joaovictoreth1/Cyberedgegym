import os
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

DEFAULT_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://joaovictoreth1.github.io",
)


@dataclass(frozen=True)
class Settings:
    database_url: str = "cyberedge.db"
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
    leads_admin_api_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        url = self.database_url
        if (
            not url.strip()
            or url == ":memory:"
            or (
                url.startswith("file:")
                and (
                    urlsplit(url).path == ":memory:"
                    or "memory" in parse_qs(urlsplit(url).query).get("mode", ())
                )
            )
        ):
            raise ValueError("DATABASE_URL must identify a persistent SQLite file")
        if "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must contain explicit origins")
        key = self.leads_admin_api_key
        if key and (len(key) < 32 or any(not 33 <= ord(char) <= 126 for char in key)):
            raise ValueError(
                "LEADS_ADMIN_API_KEY must use at least 32 printable ASCII characters without spaces"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", "cyberedge.db"),
            allowed_origins=tuple(
                origin.strip()
                for origin in os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(",")
                if origin.strip()
            ),
            leads_admin_api_key=os.getenv("LEADS_ADMIN_API_KEY", ""),
        )
