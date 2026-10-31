"""Database-backed bounded scan admission with in-process execution and recovery."""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.crawling.crawler import WebsiteCrawler
from app.models.domain import Page, ScanStatus
from app.repositories.records import Records
from app.services.static_audits import run_static_audits

logger = logging.getLogger(__name__)


def execute_scan(scan_id: UUID, session_factory=SessionLocal, crawler_factory=WebsiteCrawler):
    asyncio.run(_execute_scan(scan_id, session_factory, crawler_factory))


async def _execute_scan(scan_id, session_factory, crawler_factory):
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
            scan.audit_summary = {**scan.audit_summary, "phase": "CRAWLING"}
            session.commit()
        async with asyncio.timeout(settings.scan_duration):
            crawler = crawler_factory(
                url,
                settings.model_copy(
                    update={
                        "crawl_duration": min(
                            settings.crawl_duration, settings.scan_duration * 0.65
                        )
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

    def recover():
        with SessionLocal() as session:
            records = Records(session)
            records.expire_scans()
            from app.repositories.agent_tests import AgentRecords

            AgentRecords(session).expire()
            pending = records.pending_scans(get_settings().scan_max_active)
            session.commit()
            return pending

    try:
        while True:
            try:
                pending = await asyncio.to_thread(recover)
                if len(tasks) < get_settings().scan_max_active:
                    for scan_id in pending[: get_settings().scan_max_active - len(tasks)]:
                        task = asyncio.create_task(asyncio.to_thread(execute_scan, scan_id))
                        tasks.add(task)
                        task.add_done_callback(tasks.discard)
            except Exception:
                logger.warning("Scan recovery unavailable", exc_info=True)
            await asyncio.sleep(2)
    finally:
        # Threads cannot be forcibly stopped. Shutdown/reload recovery relies on
        # database deadlines; pending scans are retained and scheduled after restart.
        for task in tasks:
            task.cancel()
