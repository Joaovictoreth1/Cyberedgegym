import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from secrets import token_urlsafe

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from main import create_app
from middleware import ContactRateLimiter
from settings import Settings

LEAD = {
    "nome": "Pessoa Teste",
    "academia": "Academia Teste",
    "whatsapp": "11999998888",
    "tier": "pro",
}
CHANGE = {"status": "contatado", "esperado": "novo"}


def test_admin_requires_bearer(client: TestClient) -> None:
    for token in ({}, {"Authorization": "Basic bad"}, {"Authorization": "Bearer wrong"}):
        listed = client.get("/api/leads", headers=token)
        updated = client.patch("/api/leads/1", json=CHANGE, headers=token)
        assert listed.status_code == updated.status_code == 401
        assert listed.headers["WWW-Authenticate"] == "Bearer"
        assert listed.json()["error"]["code"] == "unauthorized"


def test_admin_not_configured(settings: Settings) -> None:
    with TestClient(create_app(settings.model_copy(update={"admin_token": None}))) as client:
        response = client.get("/api/leads")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "admin_disabled"


def test_cors_policy(client: TestClient) -> None:
    headers = {
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,idempotency-key",
    }
    allowed = client.options("/api/contato", headers=headers)
    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == headers["Origin"]
    assert "Access-Control-Allow-Credentials" not in allowed.headers
    denied = client.options("/api/contato", headers={**headers, "Origin": "https://example.test"})
    assert denied.status_code == 400
    assert "Access-Control-Allow-Origin" not in denied.headers
    assert (
        client.options(
            "/api/leads", headers={**headers, "Access-Control-Request-Method": "PATCH"}
        ).status_code
        == 400
    )
    assert client.get("/").headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/").headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "changes",
    [
        {"nome": " " * 2},
        {"nome": "a" * 121},
        {"academia": "nome\npartido"},
        {"whatsapp": "contato 11999998888"},
        {"whatsapp": "١٢٣٤٥٦٧٨٩٠"},
        {"unexpected": "private-value"},
    ],
)
def test_bad_fields_are_rejected_without_echo(client: TestClient, changes: dict[str, str]) -> None:
    response = client.post("/api/contato", json=LEAD | changes)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "private-value" not in response.text
    assert LEAD["whatsapp"] not in response.text


def test_body_limits_and_media_type(client: TestClient) -> None:
    headers = {"Content-Type": "application/json", "Origin": "http://localhost:5500"}
    oversized = client.post("/api/contato", content=b"x" * 4097, headers=headers)
    assert oversized.status_code == 413
    assert oversized.headers["Access-Control-Allow-Origin"] == headers["Origin"]
    chunks = (b"x" * 2500 for _ in range(2))
    assert client.post("/api/contato", content=chunks, headers=headers).status_code == 413
    assert client.post("/api/contato", content="text").status_code == 415
    assert client.post("/api/contato", content=b"{", headers=headers).status_code == 422
    assert (
        client.post("/api/contato", headers={**headers, "Content-Length": "-1"}).status_code == 400
    )


def test_rate_limit(settings: Settings) -> None:
    limited = settings.model_copy(update={"contact_rate_limit": 1})
    with TestClient(create_app(limited)) as client:
        assert client.post("/api/contato", json=LEAD).status_code == 201
        response = client.post("/api/contato", json=LEAD)
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert client.get("/readyz").status_code == 200


def test_rate_limiter_does_not_evict_active_clients() -> None:
    now = 0.0
    limiter = ContactRateLimiter(2, 15, 1, clock=lambda: now)
    assert limiter.retry_after("one") is None
    assert limiter.retry_after("two") == 15
    assert limiter.retry_after("one") is None
    assert limiter.retry_after("one") == 15
    now = 15.0
    assert limiter.retry_after("two") is None


def test_parallel_retries_and_key_conflict(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    headers = {"Idempotency-Key": "valid-retry-key-1234"}

    def submit(_: int) -> int:
        response = client.post("/api/contato", json=LEAD, headers=headers)
        assert response.status_code == 201
        return int(response.json()["id"])

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(submit, range(4)))
    assert len(set(ids)) == 1
    assert len(client.get("/api/leads", headers=admin_headers).json()) == 1
    conflict = client.post("/api/contato", json=LEAD | {"tier": "start"}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    bad = client.post("/api/contato", json=LEAD, headers={"Idempotency-Key": "short"})
    assert bad.status_code == 422


def test_status_conflict_and_filtering(client: TestClient, admin_headers: dict[str, str]) -> None:
    ids = [client.post("/api/contato", json=LEAD).json()["id"] for _ in range(3)]
    path = f"/api/leads/{ids[0]}"
    updated = client.patch(path, json=CHANGE, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "contatado"
    stale = client.patch(path, json=CHANGE, headers=admin_headers)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "status_conflict"
    assert client.patch("/api/leads/100", json=CHANGE, headers=admin_headers).status_code == 404
    page = client.get("/api/leads?sort=oldest&limit=1&offset=1", headers=admin_headers)
    assert [lead["id"] for lead in page.json()] == ids[1:2]
    filtered = client.get("/api/leads?tier=pro&status=contatado", headers=admin_headers)
    assert [lead["id"] for lead in filtered.json()] == ids[:1]
    assert [lead["id"] for lead in client.get("/api/leads", headers=admin_headers).json()] == ids[
        ::-1
    ]
    for query in (
        "limit=0",
        "limit=101",
        "offset=-1",
        "status=invalid",
        "sort=invalid",
        "extra=yes",
    ):
        assert client.get(f"/api/leads?{query}", headers=admin_headers).status_code == 422


def test_existing_sqlite_schema_is_upgraded_in_place(settings: Settings) -> None:
    with sqlite3.connect(settings.database_url) as db:
        db.execute(
            "CREATE TABLE leads (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, academia TEXT, "
            "whatsapp TEXT, tier TEXT, criado_em TEXT DEFAULT (datetime('now','localtime')), status TEXT DEFAULT 'novo')"
        )
        db.execute(
            "INSERT INTO leads (nome, academia, whatsapp, tier) VALUES (?, ?, ?, ?)",
            tuple(LEAD.values()),
        )
    assert settings.admin_token is not None
    with TestClient(create_app(settings)) as client:
        auth = {"Authorization": f"Bearer {settings.admin_token.get_secret_value()}"}
        assert client.get("/api/leads", headers=auth).json()[0]["nome"] == LEAD["nome"]
        assert client.post("/api/contato", json=LEAD).json()["id"] == 2


def test_storage_failure_does_not_leak_details(client: TestClient, settings: Settings) -> None:
    settings.database_url.unlink()
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert str(settings.database_url) not in response.text
    assert client.get("/missing").json()["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    "origin", ["*", "https://example.test/", "https://user@example.test", "https://example.test:0"]
)
def test_bad_origins_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_origins=origin)


def test_invalid_deployment_settings(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="caminho de arquivo"):
        Settings(_env_file=None, database_url=Path(":memory:"))
    invalid_token = token_urlsafe(4)
    with pytest.raises(ValidationError, match="ASCII") as error:
        Settings(_env_file=None, admin_token=SecretStr(invalid_token))
    assert invalid_token not in str(error.value)
    with pytest.raises(ValidationError, match="produção devem usar HTTPS"):
        Settings(_env_file=None, environment="production")
    with pytest.raises(ValidationError, match="obrigatório"):
        Settings(_env_file=None, environment="production", allowed_origins="")
    production = Settings(
        _env_file=None,
        environment="production",
        allowed_origins="https://example.test",
        database_url=tmp_path / "production.db",
        admin_token=SecretStr(token_urlsafe(32)),
    )
    with TestClient(create_app(production)) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/").headers["Strict-Transport-Security"] == "max-age=31536000"
