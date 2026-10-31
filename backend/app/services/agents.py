import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.agent_logging import event
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.agent.actions import TASKS
from app.engines.agent.browser import AgentScope, BrowserSession
from app.engines.agent.provider import HuggingFaceProvider
from app.engines.agent.runner import AgentRunner
from app.models.domain import AgentStep, WorkflowStatus, WorkflowTest
from app.repositories.agent_tests import AgentRecords
from app.schemas.agent import AgentTestCreate
from app.services.audits import AuditService, RecordNotFound

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, session: Session):
        self.session = session
        self.records = AgentRecords(session)

    def test(self, test_id: UUID):
        record = self.records.test(test_id)
        if record is None:
            raise RecordNotFound("Agent test not found")
        return record

    def create(self, scan_id: UUID, data: AgentTestCreate):
        scan = AuditService(self.session).scan(scan_id)
        starting_url = scan.project.website_url
        scope = AgentScope(starting_url, data.allowed_domains)
        settings = get_settings()
        test = WorkflowTest(
            scan_id=scan_id,
            task_name=data.task_type,
            task_type=data.task_type,
            task_description=TASKS[data.task_type],
            starting_url=scope.accept(starting_url),
            allowed_domains=sorted(scope.hosts),
            model_identifier=settings.agent_model,
            status=WorkflowStatus.PENDING,
            execution_deadline=datetime.now(UTC) + timedelta(seconds=settings.agent_duration + 30),
        )
        self.session.add(test)
        self.session.commit()
        return test


def execute_agent_test(
    test_id: UUID,
    session_factory=SessionLocal,
    browser_factory=BrowserSession,
    provider_factory=HuggingFaceProvider,
):
    asyncio.run(_execute(test_id, session_factory, browser_factory, provider_factory))


async def _execute(test_id, session_factory, browser_factory, provider_factory):
    runner = None
    browser = provider = None
    started = time.monotonic()
    try:
        with session_factory() as session:
            records = AgentRecords(session)
            if not records.claim(test_id):
                session.rollback()
                return
            session.commit()
            test = records.test(test_id)
            url, domains, task = test.starting_url, test.allowed_domains, test.task_description
        settings = get_settings()
        provider = provider_factory(settings)
        browser = browser_factory(url, domains, settings, str(test_id))
        runner = AgentRunner(browser, provider, settings)
        event("agent_test_started", test_id=str(test_id), model=settings.agent_model)

        def persist(data):
            with session_factory() as session:
                test = AgentRecords(session).test(test_id)
                if test is None or test.status != WorkflowStatus.RUNNING:
                    raise RuntimeError("Agent test is no longer running")
                session.add(AgentStep(workflow_test_id=test_id, **data))
                test.steps_completed = data["step_number"]
                test.final_url = data["page_url"]
                test.metrics = dict(runner.metrics)
                session.commit()

        result = await runner.run(task, url, persist)
        event(
            "agent_test_completed",
            test_id=str(test_id),
            steps=runner.steps,
            duration_seconds=round(time.monotonic() - started, 3),
        )
        finalize(
            test_id,
            WorkflowStatus.COMPLETED,
            None,
            result["outcome"],
            runner,
            time.monotonic() - started,
            session_factory,
        )
    except (Exception, asyncio.CancelledError) as exc:
        # Do not log exception bodies: provider errors may contain sensitive endpoint data.
        logger.error(
            "agent_test_failed", extra={"test_id": str(test_id), "error_type": type(exc).__name__}
        )
        message = (
            str(exc)
            if isinstance(exc, (ValueError, RuntimeError))
            else f"Agent execution failed ({type(exc).__name__})"
        )
        finalize(
            test_id,
            WorkflowStatus.FAILED,
            message[:500],
            None,
            runner,
            time.monotonic() - started,
            session_factory,
        )
        if isinstance(exc, asyncio.CancelledError):
            raise
    finally:
        # Runner owns cleanup once entered. Also handle failures during construction.
        if runner is None:
            if browser:
                await browser.close()
            if provider:
                await provider.close()


def finalize(test_id, status, error, outcome, runner, duration, factory):
    try:
        with factory() as session:
            test = AgentRecords(session).test(test_id)
            if test and test.status == WorkflowStatus.RUNNING:
                test.status, test.failure_reason = status, error
                test.completed_at = datetime.now(UTC)
                test.execution_duration = duration
                test.agent_declared_outcome = outcome
                if runner:
                    test.metrics = runner.metrics
                    test.steps_completed = runner.steps
                    test.final_url = runner.final_url or test.final_url
                session.commit()
    except SQLAlchemyError:
        logger.error("agent_test_finalization_unavailable", extra={"test_id": str(test_id)})
