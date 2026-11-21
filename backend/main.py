"""
CyberEdge Gym — Backend API
FastAPI REST API para recebimento e gestão de leads
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
import re
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="CyberEdge Gym API",
    description="API para recebimento de leads e gestão de contatos da CyberEdge Gym",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:*,https://joaovictoreth1.github.io").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Database ─────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "cyberedge.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Cria as tabelas se não existirem."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nome        TEXT NOT NULL,
                academia    TEXT NOT NULL,
                whatsapp    TEXT NOT NULL,
                tier        TEXT NOT NULL CHECK(tier IN ('start','pro','enterprise')),
                criado_em   TEXT NOT NULL DEFAULT (datetime('now')),
                status      TEXT NOT NULL DEFAULT 'novo' CHECK(status IN ('novo','contatado','fechado','perdido'))
            )
        """)

# Inicializar DB na startup
@app.on_event("startup")
def startup():
    init_db()

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
        # Remove caracteres não numéricos
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10 or len(digits) > 13:
            raise ValueError("WhatsApp inválido. Use DDD + número (ex: 11999998888)")
        return digits

    @field_validator("tier")
    @classmethod
    def valida_tier(cls, v: str) -> str:
        validos = {"start", "pro", "enterprise"}
        if v.lower() not in validos:
            raise ValueError(f"Tier inválido. Use: {', '.join(validos)}")
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
def root():
    """Health check da API."""
    return {"status": "online", "sistema": "CyberEdge Gym API", "versao": "1.0.0"}


@app.post(
    "/api/contato",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Leads"],
    summary="Registrar novo lead",
    description="Recebe os dados do formulário da landing page e persiste no banco de dados.",
)
def criar_lead(lead: LeadCreate):
    """
    Registra um novo lead recebido do formulário da landing page.

    - **nome**: Nome do gestor da academia
    - **academia**: Nome da academia
    - **whatsapp**: Número WhatsApp com DDD (apenas dígitos aceitos)
    - **tier**: Plano de interesse (start | pro | enterprise)
    """
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO leads (nome, academia, whatsapp, tier) VALUES (?, ?, ?, ?)",
            (lead.nome, lead.academia, lead.whatsapp, lead.tier),
        )
        lead_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()

    return dict(row)


@app.get(
    "/api/leads",
    response_model=list[LeadResponse],
    tags=["Admin"],
    summary="Listar todos os leads",
    description="Retorna todos os leads registrados. Proteger com autenticação em produção.",
)
def listar_leads(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Lista leads com filtros opcionais por status e tier."""
    query = "SELECT * FROM leads WHERE 1=1"
    params = []

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
