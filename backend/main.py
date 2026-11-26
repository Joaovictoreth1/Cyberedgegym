"""CyberEdge Gym lead capture API."""

import logging
import re
import secrets
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, StringConstraints, field_validator

from config import Settings

logger = logging.getLogger("uvicorn.error").getChild("cyberedge")
router = APIRouter()


@contextmanager
def connect(database_url: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_url, uri=database_url.startswith("file:"))
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(database_url: str) -> None:
    if not database_url.startswith("file:"):
        Path(database_url).parent.mkdir(parents=True, exist_ok=True)
    with connect(database_url) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nome        TEXT NOT NULL,
                academia    TEXT NOT NULL,
                whatsapp    TEXT NOT NULL,
                tier        TEXT NOT NULL CHECK(tier IN ('start','pro','enterprise')),
                criado_em   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                status      TEXT NOT NULL DEFAULT 'novo'
                            CHECK(status IN ('novo','contatado','fechado','perdido'))
            )
        """)


def get_settings(request: Request) -> Settings:
    return cast("Settings", request.app.state.settings)


Tier = Literal["start", "pro", "enterprise"]
LeadStatus = Literal["novo", "contatado", "fechado", "perdido"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Phone = Annotated[str, Field(min_length=10, max_length=32)]
AppSettings = Annotated[Settings, Depends(get_settings)]
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class LeadCreate(BaseModel):
    nome: Name
    academia: Name
    whatsapp: Phone
    tier: Tier

    @field_validator("whatsapp")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = re.sub(r"[^0-9]", "", value)
        if not re.fullmatch(r"\+?[0-9() .-]+", value.strip()) or not 10 <= len(digits) <= 13:
            raise ValueError("WhatsApp inválido. Use DDD + número.")
        return digits

    @field_validator("tier", mode="before")
    @classmethod
    def normalize_tier(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class LeadResponse(BaseModel):
    id: int
    nome: str
    academia: str
    whatsapp: str
    tier: Tier
    criado_em: str
    status: LeadStatus


def require_admin(
    settings: AppSettings, key: Annotated[str | None, Depends(api_key_header)]
) -> None:
    if not settings.leads_admin_api_key:
        raise HTTPException(status_code=503, detail="Listagem administrativa não configurada.")
    if key is None or not secrets.compare_digest(
        settings.leads_admin_api_key.encode("ascii"), key.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Chave administrativa ausente ou inválida.",
            headers={"WWW-Authenticate": "APIKey"},
        )


@router.get("/", tags=["Health"])
def health_check(settings: AppSettings) -> dict[str, str]:
    with connect(settings.database_url) as conn:
        conn.execute("SELECT 1 FROM leads LIMIT 1").fetchone()
    return {"status": "online", "sistema": "CyberEdge Gym API", "versao": "1.0.0"}


@router.post("/api/contato", status_code=201, tags=["Leads"], summary="Registrar novo lead")
def criar_lead(lead: LeadCreate, settings: AppSettings, response: Response) -> LeadResponse:
    with connect(settings.database_url) as conn:
        row = conn.execute(
            "INSERT INTO leads (nome, academia, whatsapp, tier) VALUES (?, ?, ?, ?) RETURNING *",
            (lead.nome, lead.academia, lead.whatsapp, lead.tier),
        ).fetchone()
        result = LeadResponse.model_validate(dict(row))
    response.headers["Cache-Control"] = "no-store"
    logger.info("lead_created lead_id=%d tier=%s", result.id, result.tier)
    return result


@router.get("/api/leads", tags=["Admin"], dependencies=[Depends(require_admin)])
def listar_leads(
    settings: AppSettings,
    response: Response,
    status: LeadStatus | None = None,
    tier: Tier | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[LeadResponse]:
    query = "SELECT * FROM leads WHERE 1=1"
    params: list[str | int] = []
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    if tier is not None:
        query += " AND tier = ?"
        params.append(tier)
    query += " ORDER BY criado_em DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with connect(settings.database_url) as conn:
        rows = conn.execute(query, params).fetchall()
    response.headers["Cache-Control"] = "no-store"
    return [LeadResponse.model_validate(dict(row)) for row in rows]


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_db(config.database_url)
        yield

    app = FastAPI(title="CyberEdge Gym API", version="1.0.0", lifespan=lifespan)
    app.state.settings = config
    app.include_router(router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.exception_handler(sqlite3.OperationalError)
    async def handle_database_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "database_unavailable method=%s exception=%s", request.method, type(exc).__name__
        )
        return JSONResponse(status_code=503, content={"detail": "Banco de dados indisponível."})

    return app


app = create_app()
