"""Agent request log sinks. PostgreSQL is the default; other sinks (BigQuery) plug in here."""

import hashlib
import hmac
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

import httpx

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


# Used when no VERIFICATION_SECRET is configured. A plain hash of an IPv4 address can be
# reversed by trying every address, so the fallback key is random per process: hashes stay
# stable within a run (enough for 30-minute sessions) and are never reversible.
_FALLBACK_KEY = secrets.token_bytes(32)


def client_hash(identity: str, settings: Settings) -> str:
    """Keyed hash of the client identity; the raw client address is never stored."""
    key = settings.verification_secret.get_secret_value().encode() or _FALLBACK_KEY
    return hmac.new(key, f"edge:{identity}".encode(), hashlib.sha256).hexdigest()


class PostgresRequestLogSink:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def write(self, events: list[RequestEvent]) -> None:
        with self.session_factory() as session:
            EdgeRecords(session).add_requests([AgentRequest(**event.__dict__) for event in events])
            session.commit()


# Fixed, never configurable: the Cloud Run / Compute Engine metadata server.
METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)


class MetadataToken:
    """Access token for the service's own Google service account, cached until near expiry."""

    def __init__(self, client: httpx.Client):
        self.client = client
        self.lock = threading.Lock()
        self.value, self.expires = "", 0.0

    def __call__(self) -> str:
        with self.lock:
            if time.monotonic() < self.expires:
                return self.value
            response = self.client.get(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
            response.raise_for_status()
            data = response.json()
            self.value = data["access_token"]
            self.expires = time.monotonic() + max(int(data.get("expires_in", 0)) - 60, 0)
            return self.value


class BigQueryRequestLogSink:
    """Streams events to a BigQuery table with tabledata.insertAll (no Google SDK).

    `table` is "project.dataset.table". Authentication uses the metadata server, so this
    sink is meant for Cloud Run or Compute Engine; see docs/agentlane-mvp.md for the schema.
    """

    def __init__(self, table: str, client: httpx.Client | None = None, token=None):
        project, dataset, name = table.split(".")
        self.url = (
            f"https://bigquery.googleapis.com/bigquery/v2/projects/{project}"
            f"/datasets/{dataset}/tables/{name}/insertAll"
        )
        self.client = client or httpx.Client(timeout=3, trust_env=False)
        self.token = token or MetadataToken(self.client)

    def write(self, events: list[RequestEvent]) -> None:
        rows = [
            {
                "insertId": uuid4().hex,  # Best-effort de-duplication of retried inserts.
                "json": {
                    **{
                        k: v
                        for k, v in event.__dict__.items()
                        if k not in ("site_id", "received_at")
                    },
                    "site_id": str(event.site_id),
                    "received_at": event.received_at.isoformat(),
                },
            }
            for event in events
        ]
        response = self.client.post(
            self.url,
            json={"rows": rows, "skipInvalidRows": False},
            headers={"Authorization": f"Bearer {self.token()}"},
        )
        response.raise_for_status()
        errors = response.json().get("insertErrors")
        if errors:
            raise ValueError(f"BigQuery rejected {len(errors)} of {len(rows)} rows")


class FanoutSink:
    """Writes to every sink; one failing sink never stops the others."""

    def __init__(self, sinks: list[RequestLogSink]):
        self.sinks = sinks

    def write(self, events: list[RequestEvent]) -> None:
        for sink in self.sinks:
            write_safely(sink, events)


def write_safely(sink: RequestLogSink, events: list[RequestEvent]) -> None:
    """Logging never breaks proxying: failures are reported and dropped."""
    try:
        sink.write(events)
    except Exception:  # The router fails open by design.
        logger.warning("Agent request log write failed", exc_info=True)
