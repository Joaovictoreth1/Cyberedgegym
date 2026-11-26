import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from schemas import LeadCreate, LeadQuery, LeadResponse, LeadSort, LeadStatus, LeadUpdate


class IdempotencyConflict(Exception):
    pass


class StatusConflict(Exception):
    pass


class LeadRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL").fetchone()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS leads (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome        TEXT NOT NULL,
                    academia    TEXT NOT NULL,
                    whatsapp    TEXT NOT NULL,
                    tier        TEXT NOT NULL CHECK(tier IN ('start','pro','enterprise')),
                    criado_em   TEXT NOT NULL DEFAULT (datetime('now')),
                    status      TEXT NOT NULL DEFAULT 'novo'
                                CHECK(status IN ('novo','contatado','fechado','perdido'))
                );
                CREATE INDEX IF NOT EXISTS leads_status_id ON leads(status, id);
                CREATE INDEX IF NOT EXISTS leads_tier_id ON leads(tier, id);
                CREATE INDEX IF NOT EXISTS leads_status_tier_id ON leads(status, tier, id);
                CREATE TABLE IF NOT EXISTS lead_idempotency (
                    key TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE
                );
            """)

    def ready(self) -> None:
        with self.connect() as conn:
            conn.execute("SELECT id FROM leads LIMIT 1").fetchone()

    def create(self, lead: LeadCreate, key: str | None, fingerprint: str | None) -> LeadResponse:
        with self.connect() as conn:
            if key is not None:
                conn.execute("BEGIN IMMEDIATE")
                existing = conn.execute(
                    "SELECT leads.*, request.fingerprint FROM lead_idempotency AS request "
                    "JOIN leads ON request.lead_id = leads.id WHERE request.key = ?",
                    (key,),
                ).fetchone()
                if existing is not None:
                    if existing["fingerprint"] != fingerprint:
                        raise IdempotencyConflict
                    return LeadResponse.model_validate(dict(existing) | {"status": LeadStatus.NEW})

            row = conn.execute(
                "INSERT INTO leads (nome, academia, whatsapp, tier, criado_em) "
                "VALUES (?, ?, ?, ?, datetime('now')) RETURNING *",
                (lead.nome, lead.academia, lead.whatsapp, lead.tier),
            ).fetchone()
            assert row is not None
            if key is not None:
                conn.execute(
                    "INSERT INTO lead_idempotency (key, fingerprint, lead_id) VALUES (?, ?, ?)",
                    (key, fingerprint, row["id"]),
                )
            return LeadResponse.model_validate(dict(row))

    def list(self, filters: LeadQuery) -> list[LeadResponse]:
        conditions = []
        params: list[str | int] = []
        if filters.status is not None:
            conditions.append("status = ?")
            params.append(filters.status)
        if filters.tier is not None:
            conditions.append("tier = ?")
            params.append(filters.tier)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        order = "DESC" if filters.sort == LeadSort.NEWEST else "ASC"
        params.extend((filters.limit, filters.offset))
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM leads{where} ORDER BY id {order} LIMIT ? OFFSET ?", params
            ).fetchall()
        return [LeadResponse.model_validate(dict(row)) for row in rows]

    def update(self, lead_id: int, update: LeadUpdate) -> LeadResponse | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "UPDATE leads SET status = ? WHERE id = ? AND status = ? RETURNING *",
                (update.status, lead_id, update.esperado),
            ).fetchone()
            if row is not None:
                return LeadResponse.model_validate(dict(row))
            if conn.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,)).fetchone():
                raise StatusConflict
            return None
