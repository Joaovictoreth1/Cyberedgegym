"""
CyberEdge Gym — Backend API
FastAPI REST API para recebimento e gestão de leads
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from typing import Generator, Optional

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# ── Configuração ─────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "cyberedge.db")

ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,https://joaovictoreth1.github.io",
    ).split(",")
    if origin.strip()
]


# ── Database ──────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    """Cria uma conexão SQLite.

    Suporta:
    - Arquivo normal  : "cyberedge.db"
    - Memória isolada : ":memory:"
    - Memória shared  : "file::memory:?cache=shared"  (testes com múltiplas conexões)
    """
    if DATABASE_URL.startswith("file:"):
        return sqlite3.connect(DATABASE_URL, uri=True, check_same_thread=False)
    db_dir = os.path.dirname(DATABASE_URL)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(DATABASE_URL, check_same_thread=False)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = _connect()
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Cria as tabelas se não existirem."""
    with get_db() as conn:
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


# ── Lifespan (substitui o deprecado on_event) ─────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa DB na startup; libera recursos no shutdown."""
    init_db()
    yield


# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="CyberEdge Gym API",
    description="API para recebimento de leads do formulário da landing page.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Modelos ───────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    nome: str
    academia: str
    whatsapp: str
    tier: str

    @field_validator("nome")
    @classmethod
    def nome_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nome deve ter pelo menos 2 caracteres")
        return v

    @field_validator("academia")
    @classmethod
    def academia_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Nome da academia deve ter pelo menos 2 caracteres")
        return v

    @field_validator("whatsapp")
    @classmethod
    def valida_whatsapp(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if not (10 <= len(digits) <= 13):
            raise ValueError("WhatsApp inválido. Use DDD + número (ex: 11999998888)")
        return digits

    @field_validator("tier")
    @classmethod
    def valida_tier(cls, v: str) -> str:
        validos = {"start", "pro", "enterprise"}
        if v.lower() not in validos:
            raise ValueError(f"Tier inválido. Use: {', '.join(sorted(validos))}")
        return v.lower()


class LeadResponse(BaseModel):
    id: int
    nome: str
    academia: str
    whatsapp: str
    tier: str
    criado_em: str
    status: str


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health_check() -> dict:
    """Health check — confirma que a API está online."""
    return {"status": "online", "sistema": "CyberEdge Gym API", "versao": "1.0.0"}


@app.post(
    "/api/contato",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Leads"],
    summary="Registrar novo lead",
)
def criar_lead(lead: LeadCreate) -> dict:
    """
    Recebe os dados do formulário da landing page e persiste no banco.

    - **nome**: Nome do gestor da academia
    - **academia**: Nome da academia
    - **whatsapp**: Número WhatsApp com DDD (formatações aceitas, salvo só dígitos)
    - **tier**: Plano de interesse — `start` | `pro` | `enterprise`
    """
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO leads (nome, academia, whatsapp, tier) VALUES (?, ?, ?, ?)",
            (lead.nome, lead.academia, lead.whatsapp, lead.tier),
        )
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()

    return dict(row)


@app.get(
    "/api/leads",
    response_model=list[LeadResponse],
    tags=["Admin"],
    summary="Listar leads",
)
def listar_leads(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Lista leads com filtros opcionais por `status` e `tier`."""
    query = "SELECT * FROM leads WHERE 1=1"
    params: list = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if tier:
        query += " AND tier = ?"
        params.append(tier)

    query += " ORDER BY criado_em DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]
