"""
Testes de integração — CyberEdge Gym API
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Adiciona backend ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Usar banco em memória para testes
os.environ["DATABASE_URL"] = ":memory:"

from main import app, init_db


@pytest.fixture(autouse=True)
def setup_db():
    """Inicializa banco antes de cada teste."""
    init_db()
    yield


client = TestClient(app)


# ── Health Check ──────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


# ── POST /api/contato ─────────────────────────────────────────────────

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
    assert data["tier"] == "pro"
    assert data["status"] == "novo"
    assert "id" in data
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


def test_criar_lead_nome_muito_curto():
    payload = {
        "nome": "J",
        "academia": "Academia X",
        "whatsapp": "11999998888",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_whatsapp_invalido():
    payload = {
        "nome": "Carlos Lima",
        "academia": "PowerFit",
        "whatsapp": "123",  # muito curto
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_tier_invalido():
    payload = {
        "nome": "Ana Costa",
        "academia": "GymX",
        "whatsapp": "11999998888",
        "tier": "ultra_premium",  # inválido
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_campos_obrigatorios():
    response = client.post("/api/contato", json={})
    assert response.status_code == 422


def test_criar_lead_aceita_whatsapp_formatado():
    """Deve aceitar WhatsApp com formatação como (11) 9 9999-8888"""
    payload = {
        "nome": "Pedro Alves",
        "academia": "Alpha Gym",
        "whatsapp": "(11) 9 9999-8888",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    # Deve salvar apenas dígitos
    assert response.json()["whatsapp"] == "11999998888"


# ── GET /api/leads ────────────────────────────────────────────────────

def test_listar_leads_vazio():
    response = client.get("/api/leads")
    assert response.status_code == 200
    assert response.json() == []


def test_listar_leads_apos_criar():
    # Criar lead primeiro
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
    # Criar dois leads com tiers diferentes
    client.post("/api/contato", json={"nome": "Lead PRO", "academia": "GymPro", "whatsapp": "11911112222", "tier": "pro"})
    client.post("/api/contato", json={"nome": "Lead START", "academia": "GymStart", "whatsapp": "11933334444", "tier": "start"})

    response = client.get("/api/leads?tier=pro")
    assert response.status_code == 200
    leads = response.json()
    assert all(l["tier"] == "pro" for l in leads)
