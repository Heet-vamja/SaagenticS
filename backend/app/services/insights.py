"""Phase 3: group agent traffic into sessions, label them with Gemini, summarize.

Session labels are model-judged (`label_source="gemini"`) and shown as such. Verified
task success comes only from rule-checked QA runs (services/qa.py).
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.engines.insights.labeling import label_session
from app.engines.insights.sessions import IDLE_GAP, group_requests
from app.models.domain import AgentSession
from app.repositories.edge import EdgeRecords
from app.repositories.insights import InsightRecords
from app.services.edge_sites import normalize_host

OUTCOMES = {"succeeded": "SUCCEEDED", "failed": "FAILED", "unknown": "UNKNOWN"}


def _site(session, host: str):
    site = EdgeRecords(session).site_by_host(normalize_host(host))
    if site is None:
        raise ValueError(f"{host} is not registered")
    return site


def build_sessions(host: str, session_factory) -> dict:
    """Attach unsessioned agent requests to sessions. Extending a session queues it
    for relabeling."""
    created = extended = 0
    with session_factory() as session:
        site = _site(session, host)
        records = InsightRecords(session)
        requests = records.unsessioned_agent_requests(site.id)
        by_id = {r.id: r for r in requests}
        for draft in group_requests(requests):
            existing = records.latest_session(site.id, draft.agent, draft.client_hash)
            if existing and draft.started_at - existing.ended_at <= IDLE_GAP:
                target = existing
                target.ended_at = max(existing.ended_at, draft.ended_at)
                target.request_count += len(draft.request_ids)
                target.error_count += draft.error_count
                target.variant_count += draft.variant_count
                target.label_source, target.labeled_at = "none", None
                extended += 1
            else:
                target = AgentSession(
                    site_id=site.id,
                    agent=draft.agent,
                    client_hash=draft.client_hash,
                    started_at=draft.started_at,
                    ended_at=draft.ended_at,
                    request_count=len(draft.request_ids),
                    error_count=draft.error_count,
                    variant_count=draft.variant_count,
                )
                session.add(target)
                session.flush()
                created += 1
            for request_id in draft.request_ids:
                by_id[request_id].session_id = target.id
        session.commit()
    return {"requests": len(requests), "created": created, "extended": extended}


async def label_sessions(host: str, settings: Settings, session_factory, limit: int = 20):
    """Label up to `limit` unlabeled sessions. Stops at the first inference failure."""
    labeled = 0
    with session_factory() as session:
        site = _site(session, host)
        variant = EdgeRecords(session).published_variant(site.id)
        key_tasks = [t["name"] for t in (variant.catalog.get("key_tasks", []) if variant else [])]
        pending = [
            (
                s.id,
                s.agent,
                [
                    {
                        "t": r.received_at.isoformat(timespec="seconds"),
                        "method": r.method,
                        "path": r.path,
                        "status": r.status,
                        "served_by": r.served_by,
                        "action": r.action,
                    }
                    for r in InsightRecords(session).session_requests(s.id)
                ],
            )
            for s in InsightRecords(session).unlabeled_sessions(site.id, limit)
        ]
    for session_id, agent, requests in pending:
        label, _usage = await label_session(agent, requests, key_tasks, settings)
        with session_factory() as session:
            row = session.get(AgentSession, session_id)
            row.task = label.task
            row.outcome = OUTCOMES[label.outcome]
            row.failed_step = label.failed_step
            row.explanation = label.explanation
            row.suggested_fix = label.suggested_fix
            row.label_source, row.labeled_at = "gemini", datetime.now(UTC)
            session.commit()
        labeled += 1
    return {"labeled": labeled, "remaining_in_batch": len(pending) - labeled}


def overview(host: str, session_factory, days: int = 7) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    with session_factory() as session:
        site = _site(session, host)
        records = InsightRecords(session)
        activity = records.agent_activity(site.id, since)
        sessions = records.sessions_since(site.id, since)
        variant = EdgeRecords(session).published_variant(site.id)
        qa = records.latest_qa_batch(site.id)
        sessions_by_agent = Counter(s.agent for s in sessions)
        tasks: dict[str, Counter] = defaultdict(Counter)
        failures: dict[tuple, dict] = {}
        for s in sessions:
            if s.label_source == "none":
                continue
            tasks[s.task or "Unknown task"][s.outcome] += 1
            if s.outcome == "FAILED":
                key = (s.task or "Unknown task", s.failed_step or "Unknown step")
                entry = failures.setdefault(
                    key,
                    {
                        "task": key[0],
                        "failed_step": key[1],
                        "sessions": 0,
                        "agents": set(),
                        "explanation": s.explanation,
                        "suggested_fix": s.suggested_fix,
                    },
                )
                entry["sessions"] += 1
                entry["agents"].add(s.agent)
        return {
            "site": {"host": site.host, "name": site.name, "routing_enabled": site.routing_enabled},
            "window_days": days,
            "variant": {
                "version": variant.version,
                "published_at": variant.published_at.isoformat() if variant.published_at else None,
                "products": len(variant.catalog.get("products", [])),
            }
            if variant
            else None,
            "totals": {
                "requests": sum(row.requests for row in activity),
                "agent_requests": sum(
                    row.requests for row in activity if row.agent_kind == "agent"
                ),
                "crawler_requests": sum(
                    row.requests for row in activity if row.agent_kind == "crawler"
                ),
                "variant_requests": sum(row.variant_requests or 0 for row in activity),
                "sessions": len(sessions),
                "unlabeled_sessions": sum(s.label_source == "none" for s in sessions),
            },
            "agents": [
                {
                    "agent": row.agent,
                    "kind": row.agent_kind,
                    "requests": row.requests,
                    "variant_requests": row.variant_requests or 0,
                    "errors": row.errors or 0,
                    "sessions": sessions_by_agent.get(row.agent, 0),
                    "last_seen": row.last_seen.isoformat(),
                }
                for row in activity
            ],
            "tasks": sorted(
                (
                    {
                        "task": task,
                        "sessions": sum(counts.values()),
                        "succeeded": counts["SUCCEEDED"],
                        "failed": counts["FAILED"],
                        "unknown": counts["UNKNOWN"],
                    }
                    for task, counts in tasks.items()
                ),
                key=lambda item: item["sessions"],
                reverse=True,
            )[:20],
            "failures": sorted(
                ({**f, "agents": sorted(f["agents"])} for f in failures.values()),
                key=lambda item: item["sessions"],
                reverse=True,
            )[:10],
            "qa": qa_summary(qa),
        }


def qa_summary(runs) -> dict | None:
    if not runs:
        return None
    summary = {"batch_id": str(runs[0].batch_id), "created_at": runs[0].created_at.isoformat()}
    for target in ("original", "variant"):
        rows = [r for r in runs if r.target == target]
        eligible = [r for r in rows if r.outcome != "ERROR"]
        summary[target] = {
            "runs": len(rows),
            "passed": sum(r.outcome == "PASSED" for r in rows),
            "failed": sum(r.outcome == "FAILED" for r in rows),
            "errors": sum(r.outcome == "ERROR" for r in rows),
            "eligible": len(eligible),
            "tokens": sum(r.input_tokens + r.output_tokens for r in eligible),
            "steps": sum(r.steps for r in eligible),
            "duration_ms": sum(r.duration_ms for r in eligible),
        }
    tasks = defaultdict(dict)
    for r in runs:
        tasks[r.task_key][r.target] = r.outcome
        tasks[r.task_key][f"{r.target}_steps"] = r.steps
        tasks[r.task_key]["prompt"] = r.task_prompt
    summary["tasks"] = [{"task": key, **value} for key, value in sorted(tasks.items())]
    return summary
