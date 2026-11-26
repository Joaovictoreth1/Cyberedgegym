import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Tier(StrEnum):
    START = "start"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class LeadStatus(StrEnum):
    NEW = "novo"
    CONTACTED = "contatado"
    WON = "fechado"
    LOST = "perdido"


class LeadSort(StrEnum):
    NEWEST = "newest"
    OLDEST = "oldest"


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: Annotated[str, Field(min_length=2, max_length=120)]
    academia: Annotated[str, Field(min_length=2, max_length=120)]
    whatsapp: Annotated[str, Field(min_length=10, max_length=32)]
    tier: Tier

    @field_validator("nome", "academia")
    @classmethod
    def single_line(cls, value: str) -> str:
        if not value.isprintable():
            raise ValueError("use texto de uma linha")
        return value

    @field_validator("whatsapp")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        if not re.fullmatch(r"\+?[0-9 ()-]+", value):
            raise ValueError("use apenas dígitos e pontuação de telefone")
        digits = re.sub(r"[^0-9]", "", value)
        if not 10 <= len(digits) <= 13:
            raise ValueError("use DDD + número")
        return digits

    @field_validator("tier", mode="before")
    @classmethod
    def normalize_tier(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class LeadQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LeadStatus | None = None
    tier: Tier | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 50
    offset: Annotated[int, Field(ge=0, le=100_000)] = 0
    sort: LeadSort = LeadSort.NEWEST


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: LeadStatus
    esperado: LeadStatus


class LeadResponse(BaseModel):
    id: int
    status: LeadStatus
    nome: str
    academia: str
    whatsapp: str
    tier: Tier
    criado_em: str
