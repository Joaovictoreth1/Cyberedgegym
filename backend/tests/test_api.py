from fastapi.testclient import TestClient

# ── Health Check ──────────────────────────────────────────────────────


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
