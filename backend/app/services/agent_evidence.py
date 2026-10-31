"""Opaque share-scoped references for recorded agent screenshots."""

import base64
import hashlib
import hmac
from collections.abc import Iterable
from uuid import UUID

from app.services.audits import RecordNotFound


def evidence_ref(share_token: str, scan_id: UUID, kind: str, record_id: UUID) -> str:
    key = hashlib.sha256(b"agentreadiness-share-evidence:" + share_token.encode()).digest()
    message = b"agent-evidence:" + kind.encode() + b":" + scan_id.bytes + b":" + record_id.bytes
    return (
        base64.urlsafe_b64encode(hmac.new(key, message, hashlib.sha256).digest()[:16])
        .rstrip(b"=")
        .decode("ascii")
    )


def resolve_evidence_ref(
    share_token: str, scan_id: UUID, kind: str, reference: str, candidates: Iterable[UUID]
) -> UUID:
    try:
        raw = base64.urlsafe_b64decode(reference + "=" * (-len(reference) % 4))
        if len(raw) != 16:
            raise ValueError
        for record_id in candidates:
            if hmac.compare_digest(evidence_ref(share_token, scan_id, kind, record_id), reference):
                return record_id
    except (ValueError, TypeError):
        pass
    raise RecordNotFound("Evidence not found")
