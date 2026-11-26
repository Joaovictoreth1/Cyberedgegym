from collections.abc import Iterator
from pathlib import Path
from secrets import token_urlsafe

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from main import create_app
from settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=tmp_path / "leads.db",
        admin_token=SecretStr(token_urlsafe(32)),
        allowed_origins="http://localhost:5500",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers(settings: Settings) -> dict[str, str]:
    assert settings.admin_token is not None
    return {"Authorization": f"Bearer {settings.admin_token.get_secret_value()}"}
