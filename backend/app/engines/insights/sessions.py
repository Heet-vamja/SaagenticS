"""Deterministic sessionization of logged agent requests. No model is involved."""

from dataclasses import dataclass, field
from datetime import timedelta

IDLE_GAP = timedelta(minutes=30)
MAX_REQUESTS_PER_SESSION = 500


@dataclass
class SessionDraft:
    agent: str
    client_hash: str
    request_ids: list = field(default_factory=list)
    started_at: object = None
    ended_at: object = None
    error_count: int = 0
    variant_count: int = 0


def group_requests(requests) -> list[SessionDraft]:
    """Group requests (any objects with agent, client_hash, received_at, status,
    served_by, id) by agent and client, splitting on a 30-minute idle gap."""
    open_sessions: dict[tuple[str, str], SessionDraft] = {}
    finished: list[SessionDraft] = []
    for request in sorted(requests, key=lambda r: r.received_at):
        key = (request.agent, request.client_hash)
        current = open_sessions.get(key)
        if current and (
            request.received_at - current.ended_at > IDLE_GAP
            or len(current.request_ids) >= MAX_REQUESTS_PER_SESSION
        ):
            finished.append(current)
            current = None
        if current is None:
            current = SessionDraft(
                request.agent, request.client_hash, started_at=request.received_at
            )
            open_sessions[key] = current
        current.request_ids.append(request.id)
        current.ended_at = request.received_at
        current.error_count += request.status >= 400
        current.variant_count += request.served_by == "variant"
    return finished + list(open_sessions.values())
