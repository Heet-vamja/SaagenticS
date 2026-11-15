"""Database-backed bounded scan admission with in-process execution and recovery."""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.agent.browser import BrowserSession
from app.engines.agent.provider import get_agent_provider
from app.engines.crawling.crawler import WebsiteCrawler
from app.models.domain import AgentTaskTest, Page, Scan, ScanStatus
from app.repositories.records import Records
from app.services.static_audits import run_static_audits

logger = logging.getLogger(__name__)


def finalize_interrupted_agent_scan(session, scan_id, now=None):
    """Complete a scan after its expired agent tasks have been made terminal."""
    now = now or datetime.now(UTC)
    records = Records(session)
    scan = records.scan(scan_id)
    if (
        scan is None
        or scan.status != ScanStatus.RUNNING
        or (scan.audit_summary or {}).get("phase") != "AGENT_TASKS"
    ):
        return False
    active_tasks = session.scalar(
        select(func.count())
        .select_from(AgentTaskTest)
        .where(
            AgentTaskTest.scan_id == scan_id,
            AgentTaskTest.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
        )
    )
    if active_tasks:
        return False
    reason = "Agent execution was interrupted; static results were retained."
    summary = dict(scan.audit_summary or {})
    summary["phase"] = "COMPLETED"
    summary["agent_stage"] = {"status": "UNAVAILABLE", "reason": reason}
    component = dict(summary.get("agent") or {})
    component["fallback_reason"] = reason
    component["provisional"] = True
    summary["agent"] = component
    scan.audit_summary = summary
    scan.status = ScanStatus.COMPLETED
    scan.error_summary = None
    scan.completed_at = now
    return True


def execute_scan(
    scan_id: UUID,
    session_factory=SessionLocal,
    crawler_factory=WebsiteCrawler,
    agent_browser_factory=BrowserSession,
    agent_provider_factory=get_agent_provider,
):
    asyncio.run(
        _execute_scan(
            scan_id,
            session_factory,
            crawler_factory,
            agent_browser_factory,
            agent_provider_factory,
        )
    )


async def _execute_scan(
    scan_id,
    session_factory,
    crawler_factory,
    agent_browser_factory=BrowserSession,
    agent_provider_factory=get_agent_provider,
):
    settings = get_settings()
    crawler = None
    claimed = False
    try:
        with session_factory() as session:
            records = Records(session)
            if not records.claim_scan(scan_id):
                session.rollback()
                return
            claimed = True
            scan = records.scan(scan_id)
            url = records.project(scan.project_id).website_url
            free_report_scan = (scan.audit_summary or {}).get("scan_mode") == "FREE_REPORT"
            crawl_max_pages = (
                min(settings.crawl_max_pages, 10) if free_report_scan else settings.crawl_max_pages
            )
            scan.audit_summary = {
                **scan.audit_summary,
                "phase": "CRAWLING",
                "pages_discovered": scan.pages_discovered,
                "pages_crawled": scan.pages_crawled,
                "pages_failed": scan.pages_failed,
            }
            session.commit()
        async with asyncio.timeout(settings.scan_duration):
            crawler = crawler_factory(
                url,
                settings.model_copy(
                    update={
                        "crawl_max_pages": crawl_max_pages,
                        "crawl_duration": min(
                            settings.crawl_duration, settings.scan_duration * 0.65
                        ),
                    }
                ),
            )

            def persist(record):
                with session_factory() as session:
                    records = Records(session)
                    scan = records.scan(scan_id)
                    if scan is None or scan.status != ScanStatus.RUNNING:
                        raise RuntimeError("Scan is no longer running")
                    if records.page_by_url(scan_id, record["url"]) is None:
                        if record.get("content_type"):
                            record["content_type"] = record["content_type"][:255]

                        def clean(value):
                            if isinstance(value, str):
                                return value.replace("\x00", "")
                            if isinstance(value, dict):
                                return {key: clean(item) for key, item in value.items()}
                            if isinstance(value, list):
                                return [clean(item) for item in value]
                            return value

                        session.add(Page(scan_id=scan_id, **clean(record)))
                        session.commit()

            def progress(state):
                with session_factory() as session:
                    scan = Records(session).scan(scan_id)
                    if scan is None or scan.status != ScanStatus.RUNNING:
                        raise RuntimeError("Scan is no longer running")
                    scan.pages_discovered = len(state.discovered)
                    scan.pages_crawled = state.crawled
                    scan.pages_failed = state.failed
                    scan.crawl_metadata = state.metadata()
                    session.commit()

            crawl_error = None
            try:
                await crawler.crawl(persist, progress)
            except Exception as exc:
                logger.exception("Crawl stage failed scan=%s type=%s", scan_id, type(exc).__name__)
                crawl_error = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else f"Crawl interrupted ({type(exc).__name__})"
                )
            progress(crawler)
            transport = getattr(getattr(crawler, "fetcher", None), "client", None)
            transport = getattr(transport, "_transport", None)
            # Only test fixtures share a mock transport. Production rendering creates
            # a fresh validated transport; it never reuses a closed connection pool.
            await run_static_audits(
                scan_id,
                settings,
                session_factory,
                transport if isinstance(transport, httpx.MockTransport) else None,
            )
        if not free_report_scan and not settings.customer_mode_enabled:
            # Agent tests are a separate stage with their own frozen budget. Any
            # provider/browser failure is represented as unavailable agent evidence;
            # it must not turn a completed static scan into a failed scan.
            from app.services.agents import run_scan_agent_stage

            await run_scan_agent_stage(
                scan_id,
                settings,
                session_factory,
                agent_browser_factory,
                agent_provider_factory,
            )
        finish_scan(
            scan_id,
            ScanStatus.FAILED if crawl_error else ScanStatus.COMPLETED,
            crawl_error,
            session_factory,
            crawler,
        )
    except (Exception, asyncio.CancelledError) as exc:
        if claimed:
            logger.exception("Scan execution failed scan=%s type=%s", scan_id, type(exc).__name__)
            message = (
                "Scan exceeded its total time budget; partial evidence is retained"
                if isinstance(exc, TimeoutError)
                else (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else f"Scan interrupted ({type(exc).__name__})"
                )
            )
            finish_scan(scan_id, ScanStatus.FAILED, message, session_factory, crawler)
        if isinstance(exc, asyncio.CancelledError):
            raise


def finish_scan(scan_id, status, error, session_factory, crawler):
    try:
        with session_factory() as session:
            scan = Records(session).scan(scan_id)
            if scan and scan.status == ScanStatus.RUNNING:
                scan.status = status
                scan.error_summary = error
                scan.completed_at = datetime.now(UTC)
                if crawler:
                    scan.crawl_metadata = crawler.metadata()
                    scan.pages_discovered = len(crawler.discovered)
                    scan.pages_crawled = crawler.crawled
                    scan.pages_failed = crawler.failed
                scan.audit_summary = {
                    **scan.audit_summary,
                    "phase": "COMPLETED" if status == ScanStatus.COMPLETED else "FAILED",
                }
                session.commit()
    except Exception:
        logger.exception("Unable to finalize scan %s; deadline recovery required", scan_id)


async def recover_expired_scans():
    """Reschedule durable pending work; atomic DB admission prevents double execution."""
    tasks = set()
    agent_tasks = {}

    def recover():
        with SessionLocal() as session:
            records = Records(session)
            records.expire_scans()
            from app.repositories.agent_tests import AgentRecords

            expired_task_scans = set(
                session.scalars(
                    select(AgentTaskTest.scan_id).where(
                        AgentTaskTest.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
                        AgentTaskTest.deadline < datetime.now(UTC),
                    )
                )
            )
            AgentRecords(session).expire()
            for scan_id in expired_task_scans:
                finalize_interrupted_agent_scan(session, scan_id)
            eligible = select(Scan.id).where(
                Scan.id == AgentTaskTest.scan_id,
                Scan.status == ScanStatus.COMPLETED,
            )
            agent_ids = list(
                session.scalars(
                    select(AgentTaskTest.id)
                    .where(
                        AgentTaskTest.status == ScanStatus.PENDING,
                        AgentTaskTest.scan_id.in_(eligible),
                    )
                    .order_by(AgentTaskTest.created_at, AgentTaskTest.id)
                    .limit(get_settings().agent_max_active)
                )
            )
            if get_settings().customer_mode_enabled:
                agent_ids = []  # Do not resume legacy agent jobs in the customer release.
            pending = records.pending_scans(get_settings().scan_max_active)
            session.commit()
            return pending, agent_ids, set(expired_task_scans)

    try:
        while True:
            try:
                pending, agent_ids, expired_task_scans = await asyncio.to_thread(recover)
                for scan_id in expired_task_scans:
                    from app.services.agents import refresh_agent_score

                    await asyncio.to_thread(refresh_agent_score, scan_id)
                if len(tasks) < get_settings().scan_max_active:
                    for scan_id in pending[: get_settings().scan_max_active - len(tasks)]:
                        task = asyncio.create_task(asyncio.to_thread(execute_scan, scan_id))
                        tasks.add(task)
                        task.add_done_callback(tasks.discard)
                from app.services.agents import execute_agent_task

                for task_id in agent_ids:
                    if (
                        task_id not in agent_tasks
                        and len(agent_tasks) < get_settings().agent_max_active
                    ):
                        job = asyncio.create_task(asyncio.to_thread(execute_agent_task, task_id))
                        agent_tasks[task_id] = job
                        job.add_done_callback(lambda _, key=task_id: agent_tasks.pop(key, None))
            except Exception:
                logger.warning("Scan recovery unavailable", exc_info=True)
            await asyncio.sleep(2)
    finally:
        # Threads cannot be forcibly stopped. Shutdown/reload recovery relies on
        # database deadlines; pending scans are retained and scheduled after restart.
        for task in tasks:
            task.cancel()
        for task in agent_tasks.values():
            task.cancel()
