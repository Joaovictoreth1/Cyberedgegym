import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import Settings
from main import connect, create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=str(tmp_path / "storage" / "test.db"),
        leads_admin_api_key=secrets.token_urlsafe(32),
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def admin_headers(settings: Settings) -> dict[str, str]:
    return {"X-API-Key": settings.leads_admin_api_key}


def test_health_check(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


# ── POST /api/contato — casos de sucesso ──────────────────────────────


def test_criar_lead_sucesso(client: TestClient) -> None:
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


def test_criar_lead_tier_enterprise(client: TestClient) -> None:
    payload = {
        "nome": "Maria Santos",
        "academia": "MegaFit 5000",
        "whatsapp": "21988887777",
        "tier": "enterprise",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    assert response.json()["tier"] == "enterprise"


def test_criar_lead_tier_start(client: TestClient) -> None:
    payload = {
        "nome": "Carlos Lima",
        "academia": "Start Gym",
        "whatsapp": "31977776666",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 201
    assert response.json()["tier"] == "start"


def test_criar_lead_aceita_whatsapp_formatado(client: TestClient) -> None:
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


def test_criar_lead_nome_muito_curto(client: TestClient) -> None:
    payload = {
        "nome": "J",  # menos de 2 chars
        "academia": "Academia X",
        "whatsapp": "11999998888",
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_whatsapp_curto_demais(client: TestClient) -> None:
    payload = {
        "nome": "Ana Costa",
        "academia": "PowerFit",
        "whatsapp": "123",  # menos de 10 dígitos
        "tier": "start",
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_tier_invalido(client: TestClient) -> None:
    payload = {
        "nome": "Ana Costa",
        "academia": "GymX",
        "whatsapp": "11999998888",
        "tier": "ultra_premium",  # não existe
    }
    response = client.post("/api/contato", json=payload)
    assert response.status_code == 422


def test_criar_lead_campos_obrigatorios(client: TestClient) -> None:
    response = client.post("/api/contato", json={})
    assert response.status_code == 422


# ── GET /api/leads ────────────────────────────────────────────────────


def test_listar_leads_vazio(client: TestClient, admin_headers: dict[str, str]) -> None:
    response = client.get("/api/leads", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_listar_leads_apos_criar(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.post(
        "/api/contato",
        json={
            "nome": "Teste Listagem",
            "academia": "Gym List",
            "whatsapp": "11911112222",
            "tier": "start",
        },
    )
    response = client.get("/api/leads", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    leads = response.json()
    assert len(leads) == 1
    assert leads[0]["nome"] == "Teste Listagem"


def test_listar_leads_filtro_tier(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.post(
        "/api/contato",
        json={
            "nome": "Lead PRO",
            "academia": "GymPro",
            "whatsapp": "11911112222",
            "tier": "pro",
        },
    )
    client.post(
        "/api/contato",
        json={
            "nome": "Lead START",
            "academia": "GymStart",
            "whatsapp": "11933334444",
            "tier": "start",
        },
    )

    response = client.get("/api/leads?tier=pro", headers=admin_headers)
    assert response.status_code == 200
    leads = response.json()
    assert len(leads) == 1
    assert leads[0]["tier"] == "pro"


LEAD = {"nome": "João Silva", "academia": "Academia X", "whatsapp": "11999998888", "tier": "pro"}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_lead_list_requires_admin(client: TestClient, headers: dict[str, str]) -> None:
    assert client.post("/api/contato", json=LEAD).status_code == 201
    denied = client.get("/api/leads", headers=headers)
    assert denied.status_code == 401
    assert denied.headers["WWW-Authenticate"] == "APIKey"
    assert LEAD["whatsapp"] not in denied.text


def test_capture_stays_public_when_admin_is_disabled(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(database_url=str(tmp_path / "data.db")))) as client:
        assert client.post("/api/contato", json=LEAD).status_code == 201
        assert client.get("/api/leads").status_code == 503


@pytest.mark.parametrize(
    "params", ["limit=0", "limit=101", "offset=-1", "offset=1000001", "status=bad", "tier=bad"]
)
def test_invalid_list_filters(
    client: TestClient, admin_headers: dict[str, str], params: str
) -> None:
    assert client.get(f"/api/leads?{params}", headers=admin_headers).status_code == 422


def test_pagination_is_ordered_even_when_timestamps_tie(
    client: TestClient, settings: Settings, admin_headers: dict[str, str]
) -> None:
    ids = [client.post("/api/contato", json=LEAD).json()["id"] for _ in range(3)]
    with connect(settings.database_url) as conn:
        conn.execute("UPDATE leads SET criado_em = '2026-01-01 00:00:00', status = 'contatado'")
    page = client.get("/api/leads?status=contatado&limit=1&offset=1", headers=admin_headers)
    assert page.status_code == 200
    assert [lead["id"] for lead in page.json()] == [ids[1]]


@pytest.mark.parametrize(
    "fields", [{"whatsapp": "fake11999998888"}, {"nome": "a" * 121}, {"academia": "  "}]
)
def test_lead_rejects_bad_input(client: TestClient, fields: dict[str, str]) -> None:
    assert client.post("/api/contato", json={**LEAD, **fields}).status_code == 422


def test_storage_failure_returns_safe_503(client: TestClient, settings: Settings) -> None:
    with connect(settings.database_url) as conn:
        conn.execute("DROP TABLE leads")
    response = client.post("/api/contato", json=LEAD)
    assert response.status_code == 503
    assert response.json() == {"detail": "Banco de dados indisponível."}
    assert client.get("/").status_code == 503


def test_browser_preflight_from_pages(client: TestClient) -> None:
    headers = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    origin = "https://joaovictoreth1.github.io"
    allowed = client.options("/api/contato", headers={**headers, "Origin": origin})
    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == origin
    rejected = client.options(
        "/api/contato", headers={**headers, "Origin": "https://other.example"}
    )
    assert rejected.status_code == 400
    assert "Access-Control-Allow-Origin" not in rejected.headers


def test_invalid_configured_admin_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEADS_ADMIN_API_KEY", "too-short")
    with pytest.raises(ValueError, match="LEADS_ADMIN_API_KEY"):
        create_app()
