"""
Testes de integração — CyberEdge Gym API

Estratégia de banco nos testes:
- Usamos um arquivo temporário real (tempfile.mktemp) por sessão de testes.
- O arquivo é criado na fixture de sessão, inicializado com init_db(),
  e deletado no teardown. Cada teste limpa os dados mas mantém o schema.
- Isso evita o problema do SQLite :memory: (banco novo por conexão) e
  do shared-cache (pode não funcionar no Windows).
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

# ── Configura banco ANTES de importar main ────────────────────────────
_tmp_db = tempfile.mktemp(suffix=".test.db", prefix="cyberedge_")
os.environ["DATABASE_URL"] = _tmp_db

# Garante que o diretório do backend está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app, init_db, get_db  # noqa: E402  (import após set env)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def criar_schema():
    """Cria o schema uma vez por sessão de testes."""
    init_db()
    yield
    # Teardown: remove arquivo de banco temporário
    if os.path.exists(_tmp_db):
        os.remove(_tmp_db)


@pytest.fixture(autouse=True)
def banco_limpo():
    """Limpa os dados antes de cada teste (mantém schema)."""
    with get_db() as conn:
        conn.execute("DELETE FROM leads")
    yield


client = TestClient(app)


# ── Health Check ──────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


# ── POST /api/contato — casos de sucesso ──────────────────────────────

def test_criar_lead_sucesso():
    payload = {
        "nome": "João Silva",
        "academia": "FitZone Academia",
        "whatsapp": "11999998888",
        "tier": "pro",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["nome"] == "João Silva"
    assert data["academia"] == "FitZone Academia"
    assert data["whatsapp"] == "11999998888"
    assert data["tier"] == "pro"
    assert data["status"] == "novo"
    assert isinstance(data["id"], int)
    assert "criado_em" in data


def test_criar_lead_tier_enterprise():
    payload = {
        "nome": "Maria Santos",
        "academia": "MegaFit 5000",
        "whatsapp": "21988887777",
        "tier": "enterprise",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    assert response.json()["tier"] == "enterprise"


def test_criar_lead_tier_start():
    payload = {
        "nome": "Carlos Lima",
        "academia": "Start Gym",
        "whatsapp": "31977776666",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    assert response.json()["tier"] == "start"


def test_criar_lead_aceita_whatsapp_formatado():
    """Deve aceitar WhatsApp com formatação como (11) 9 9999-8888."""
    payload = {
        "nome": "Pedro Alves",
        "academia": "Alpha Gym",
        "whatsapp": "(11) 9 9999-8888",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    # Deve salvar somente dígitos
    assert response.json()["whatsapp"] == "11999998888"


# ── POST /api/contato — validações (422) ──────────────────────────────

def test_criar_lead_nome_muito_curto():
    payload = {
        "nome": "J",   # menos de 2 chars
        "academia": "Academia X",
        "whatsapp": "11999998888",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_whatsapp_curto_demais():
    payload = {
        "nome": "Ana Costa",
        "academia": "PowerFit",
        "whatsapp": "123",   # menos de 10 dígitos
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_tier_invalido():
    payload = {
        "nome": "Ana Costa",
        "academia": "GymX",
        "whatsapp": "11999998888",
        "tier": "ultra_premium",   # não existe
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_campos_obrigatorios():
    response = client.post("/api/contato", json={})
    assert response.status_code == 422


# ── GET /api/leads ────────────────────────────────────────────────────

def test_listar_leads_vazio():
    response = client.get("/api/leads")
    assert response.status_code == 200
    assert response.json() == []


def test_listar_leads_apos_criar():
    client.post("/api/contato", json={
        "nome": "Teste Listagem",
        "academia": "Gym List",
        "whatsapp": "11911112222",
        "tier": "start",
    })
    response = client.get("/api/leads")
    assert response.status_code == 200
    leads = response.json()
    assert len(leads) == 1
    assert leads[0]["nome"] == "Teste Listagem"


def test_listar_leads_filtro_tier():
    client.post("/api/contato", json={
        "nome": "Lead PRO", "academia": "GymPro",
        "whatsapp": "11911112222", "tier": "pro",
    })
    client.post("/api/contato", json={
        "nome": "Lead START", "academia": "GymStart",
        "whatsapp": "11933334444", "tier": "start",
    })

    response = client.get("/api/leads?tier=pro")
    assert response.status_code == 200
    leads = response.json()
    assert len(leads) == 1
    assert leads[0]["tier"] == "pro"
