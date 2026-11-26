"""Application entry point for the CyberEdge Gym lead API."""

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Path, Query, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from errors import ApiError, error_response
from middleware import RequestLimitsMiddleware, SecurityHeadersMiddleware
from repository import LeadRepository
from schemas import LeadCreate, LeadQuery, LeadResponse, LeadUpdate
from service import LeadService
from settings import Settings

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)
VALIDATION_FIELDS = frozenset(
    {
        "nome",
        "academia",
        "whatsapp",
        "tier",
        "status",
        "esperado",
        "sort",
        "limit",
        "offset",
        "lead_id",
        "idempotency-key",
    }
)


def create_app(settings: Settings) -> FastAPI:
    repository = LeadRepository(settings.database_url)
    service = LeadService(repository)
    production = settings.environment == "production"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await run_in_threadpool(repository.initialize)
        yield

    app = FastAPI(
        title="CyberEdge Gym API",
        version="1.1.0",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLimitsMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
        expose_headers=["Retry-After"],
    )
    app.add_middleware(SecurityHeadersMiddleware, production=production)

    def require_admin(
        authorization: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
    ) -> None:
        token = settings.admin_token
        if token is None:
            raise ApiError(503, "admin_disabled", "Acesso administrativo não configurado.")
        if authorization is None or not compare_digest(
            authorization.credentials.encode(), token.get_secret_value().encode()
        ):
            raise ApiError(
                401, "unauthorized", "Credenciais inválidas.", {"WWW-Authenticate": "Bearer"}
            )

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, error: ApiError) -> JSONResponse:
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, error: RequestValidationError) -> JSONResponse:
        fields = []
        for problem in error.errors():
            location = problem.get("loc", ())
            name = str(location[-1]) if len(location) > 1 else "request"
            fields.append(
                {"field": name if name in VALIDATION_FIELDS else "request", "code": problem["type"]}
            )
        return error_response(
            ApiError(422, "invalid_request", "Verifique os campos da solicitação."), fields
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(_: Request, error: HTTPException) -> JSONResponse:
        code, message = {
            404: ("not_found", "Rota não encontrada."),
            405: ("method_not_allowed", "Método não permitido."),
        }.get(error.status_code, ("http_error", "Solicitação não concluída."))
        return error_response(ApiError(error.status_code, code, message, error.headers))

    @app.exception_handler(sqlite3.Error)
    async def handle_db_error(_: Request, error: sqlite3.Error) -> JSONResponse:
        logger.error("SQLite request failed (%s)", type(error).__name__)
        return error_response(ApiError(503, "storage_unavailable", "Armazenamento indisponível."))

    @app.get("/", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "online", "sistema": "CyberEdge Gym API", "versao": app.version}

    @app.get("/readyz", tags=["Health"])
    def readiness() -> dict[str, str]:
        repository.ready()
        return {"status": "ready"}

    @app.post("/api/contato", status_code=201, tags=["Leads"])
    def criar_lead(
        lead: LeadCreate,
        idempotency_key: Annotated[
            str | None, Header(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
        ] = None,
    ) -> LeadResponse:
        return service.create(lead, idempotency_key)

    @app.get("/api/leads", tags=["Admin"], dependencies=[Depends(require_admin)])
    def listar_leads(filters: Annotated[LeadQuery, Query()]) -> list[LeadResponse]:
        return service.list(filters)

    @app.patch("/api/leads/{lead_id}", tags=["Admin"], dependencies=[Depends(require_admin)])
    def atualizar_lead(
        lead_id: Annotated[int, Path(ge=1, le=2**63 - 1)], update: LeadUpdate
    ) -> LeadResponse:
        return service.update(lead_id, update)

    return app


app = create_app(Settings())
