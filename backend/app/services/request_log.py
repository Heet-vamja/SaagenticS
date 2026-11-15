"""Agent request log sinks. PostgreSQL is the default; other sinks (BigQuery) plug in here."""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.core.config import Settings
from app.models.domain import AgentRequest
from app.repositories.edge import EdgeRecords

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestEvent:
    site_id: UUID
    received_at: datetime
    agent: str
    agent_kind: str
    method: str
    path: str
    status: int
    duration_ms: int
    served_by: str
    response_bytes: int
    client_hash: str
    user_agent: str
    action: str | None = None


class RequestLogSink(Protocol):
    def write(self, events: list[RequestEvent]) -> None: ...


def client_hash(identity: str, settings: Settings) -> str:
    """Keyed hash when a secret is configured; never store the raw client address."""
    key = settings.verification_secret.get_secret_value().encode()
    if key:
        return hmac.new(key, f"edge:{identity}".encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(f"edge:{identity}".encode()).hexdigest()


class PostgresRequestLogSink:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def write(self, events: list[RequestEvent]) -> None:
        with self.session_factory() as session:
            EdgeRecords(session).add_requests([AgentRequest(**event.__dict__) for event in events])
            session.commit()


def write_safely(sink: RequestLogSink, events: list[RequestEvent]) -> None:
    """Logging never breaks proxying: failures are reported and dropped."""
    try:
        sink.write(events)
    except Exception:  # The router fails open by design.
        logger.warning("Agent request log write failed", exc_info=True)
