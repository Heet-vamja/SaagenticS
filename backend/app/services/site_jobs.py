"""Dashboard-started jobs (phase 5): queued by the API, run by the jobs worker.

The API only persists a PENDING job. The worker (`python -m app.cli.jobs worker`) runs
where Gemini is configured and the router is reachable, claims jobs with
`FOR UPDATE SKIP LOCKED` and records the real outcome. A job that outlives
`job_max_duration` is marked FAILED. Nothing is retried automatically or reported as
done without actually running.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from playwright.async_api import Error as PlaywrightError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.engines.agent.provider import InferenceError
from app.models.domain import SiteJob
from app.repositories.edge import EdgeRecords
from app.repositories.site_jobs import JobRecords
from app.services.edge_sites import normalize_host
from app.services.insights import build_sessions, label_sessions
from app.services.qa import run_qa
from app.services.variants import build_variant

logger = logging.getLogger(__name__)
KINDS = ("build_variant", "label_sessions", "run_qa")
# Errors whose messages are ours and safe to show the owner. Anything else is reported
# by type only.
EXPECTED = (InferenceError, ValueError, TimeoutError, OSError, PlaywrightError)


class JobConflict(Exception):
    pass


def _site(session: Session, host: str):
    site = EdgeRecords(session).site_by_host(normalize_host(host))
    if site is None:
        raise ValueError(f"{host} is not registered")
    return site


def job_view(job: SiteJob) -> dict:
    def stamp(value):
        return value.isoformat() if value else None

    return {
        "id": str(job.id),
        "kind": job.kind,
        "status": job.status,
        "result": job.result,
        "detail": job.detail,
        "created_at": stamp(job.created_at),
        "started_at": stamp(job.started_at),
        "finished_at": stamp(job.finished_at),
    }


def enqueue(session: Session, host: str, kind: str) -> SiteJob:
    if kind not in KINDS:
        raise ValueError("Unknown job kind")
    site = _site(session, host)
    try:
        with session.begin_nested():
            job = JobRecords(session).add(SiteJob(site_id=site.id, kind=kind))
    except IntegrityError as exc:
        raise JobConflict("This job is already queued or running for this site") from exc
    session.commit()
    session.refresh(job)
    return job


def recent_jobs(session: Session, host: str, limit: int = 10) -> list[SiteJob]:
    return JobRecords(session).recent(_site(session, host).id, limit)


def expire_stale(session_factory, settings: Settings) -> int:
    now = datetime.now(UTC)
    with session_factory() as session:
        count = JobRecords(session).fail_running_before(
            now - timedelta(seconds=settings.job_max_duration),
            "Stopped: the job ran longer than the allowed time",
            now,
        )
        session.commit()
    return count


def claim_next(session_factory) -> tuple | None:
    """Mark the oldest pending job RUNNING and return (job_id, kind, host)."""
    with session_factory() as session:
        records = JobRecords(session)
        job = records.next_pending()
        if job is None:
            return None
        job.status, job.started_at = "RUNNING", datetime.now(UTC)
        claimed = (job.id, job.kind, records.host_of(job.site_id))
        session.commit()
        return claimed


def _finish(session_factory, job_id, status: str, result=None, detail=None) -> None:
    with session_factory() as session:
        job = session.get(SiteJob, job_id)
        job.status, job.result, job.finished_at = status, result, datetime.now(UTC)
        job.detail = detail[:300] if detail else None
        session.commit()


async def _execute(kind: str, host: str, settings: Settings, session_factory) -> dict:
    if kind == "build_variant":
        built = await build_variant(host, settings, session_factory, publish=True)
        return {
            "version": built.version,
            "status": built.status,
            "pages": built.pages,
            "products": built.products,
            "parity_passed": bool(built.parity.get("passed")),
        }
    if kind == "label_sessions":
        grouped = build_sessions(host, session_factory)
        labeled = await label_sessions(host, settings, session_factory)
        return {"sessions": grouped, **labeled}
    base_url = settings.qa_base_url_template.format(host=host)
    summary = await run_qa(host, base_url, settings, session_factory)
    if summary is None:
        raise ValueError("QA produced no runs")
    return {
        target: {key: summary[target][key] for key in ("passed", "eligible", "errors")}
        for target in ("original", "variant")
    }


async def run_claimed(job_id, kind: str, host: str, settings: Settings, session_factory) -> str:
    """Run one claimed job to a recorded SUCCEEDED or FAILED state."""
    try:
        async with asyncio.timeout(settings.job_max_duration):
            result = await _execute(kind, host, settings, session_factory)
    except EXPECTED as exc:
        _finish(session_factory, job_id, "FAILED", detail=f"{type(exc).__name__}: {exc}")
        return "FAILED"
    except Exception as exc:  # The worker must survive any single job.
        logger.exception("Site job %s failed", job_id)
        _finish(
            session_factory, job_id, "FAILED", detail=f"Unexpected error ({type(exc).__name__})"
        )
        return "FAILED"
    # A rejected variant build is a real outcome, recorded as a finished job with the
    # parity report; the dashboard shows it as rejected, not as a published lane.
    _finish(session_factory, job_id, "SUCCEEDED", result=result)
    return "SUCCEEDED"


async def work(settings: Settings, session_factory, once: bool = False) -> None:
    while True:
        expire_stale(session_factory, settings)
        claimed = claim_next(session_factory)
        if claimed:
            job_id, kind, host = claimed
            logger.info("Running %s for %s", kind, host)
            status = await run_claimed(job_id, kind, host, settings, session_factory)
            logger.info("Finished %s for %s: %s", kind, host, status)
        if once:
            return
        if not claimed:
            await asyncio.sleep(settings.jobs_poll_interval)
