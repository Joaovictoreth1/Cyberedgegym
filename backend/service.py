from hashlib import sha256

from errors import ApiError
from repository import IdempotencyConflict, LeadRepository, StatusConflict
from schemas import LeadCreate, LeadQuery, LeadResponse, LeadUpdate


class LeadService:
    def __init__(self, repository: LeadRepository) -> None:
        self.repository = repository

    def create(self, lead: LeadCreate, key: str | None) -> LeadResponse:
        fingerprint = sha256(lead.model_dump_json().encode()).hexdigest() if key else None
        try:
            return self.repository.create(lead, key, fingerprint)
        except IdempotencyConflict as exc:
            raise ApiError(409, "idempotency_conflict", "Chave já usada com outros dados.") from exc

    def list(self, filters: LeadQuery) -> list[LeadResponse]:
        return self.repository.list(filters)

    def update(self, lead_id: int, update: LeadUpdate) -> LeadResponse:
        try:
            lead = self.repository.update(lead_id, update)
        except StatusConflict as exc:
            raise ApiError(409, "status_conflict", "Status atual diferente do esperado.") from exc
        if lead is None:
            raise ApiError(404, "lead_not_found", "Lead não encontrado.")
        return lead
