"""Task/run orchestration with independent sessions and infrastructure-safe results."""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.agent_logging import event
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.agent.actions import TASKS
from app.engines.agent.browser import AgentScope, BrowserSession
from app.engines.agent.contracts import RunResult
from app.engines.agent.privacy import public_url, redact, sanitize
from app.engines.agent.provider import InferenceError, get_agent_provider
from app.engines.agent.runner import AgentRunner
from app.models.domain import (
    AgentStep,
    AgentTaskTest,
    Scan,
    ScanStatus,
    WorkflowStatus,
    WorkflowTest,
)
from app.repositories.agent_tests import AgentRecords
from app.repositories.records import Records
from app.schemas.agent import AgentTaskCreate, AgentTestCreate
from app.services.agent_policy import consume_admission, snapshot
from app.services.agent_results import aggregate, blend
from app.services.audits import AuditService, RecordNotFound

logger = logging.getLogger(__name__)
ACTIVE = (ScanStatus.PENDING, ScanStatus.RUNNING)


class AgentService:
    def __init__(self, session: Session):
        self.session = session
        self.records = AgentRecords(session)

    def test(self, test_id: UUID):
        result = self.records.test(test_id)
        if result is None:
            raise RecordNotFound("Agent test not found")
        return result

    def task(self, task_id: UUID):
        result = self.records.task(task_id)
        if result is None:
            raise RecordNotFound("Agent task not found")
        return result

    def create_task(
        self, scan_id: UUID, data: AgentTaskCreate, identity="local", automatic=False, legacy=False
    ):
        scan = AuditService(self.session).scan(scan_id)
        settings = get_settings()
        policy = dict(scan.audit_summary.get("agent_policy") or snapshot(settings))
        Records(self.session).admission_lock()
        existing = self.session.scalar(
            select(AgentTaskTest)
            .where(
                AgentTaskTest.scan_id == scan_id,
                AgentTaskTest.task_type == data.task_type,
                AgentTaskTest.status.in_(ACTIVE),
            )
            .order_by(AgentTaskTest.created_at)
        )
        if existing:
            self.session.commit()
            return existing
        if automatic:
            existing = self.session.scalar(
                select(AgentTaskTest)
                .where(AgentTaskTest.scan_id == scan_id, AgentTaskTest.task_type == data.task_type)
                .order_by(AgentTaskTest.created_at)
            )
            if existing:
                self.session.commit()
                return existing
        if not automatic and scan.status in ACTIVE and not legacy:
            raise HTTPException(
                409, "Wait for the scan pipeline to finish before starting another task"
            )
        count = self.session.scalar(
            select(func.count()).select_from(AgentTaskTest).where(AgentTaskTest.scan_id == scan_id)
        )
        if policy["free_limits_enabled"] and count >= policy["task_limit"]:
            raise HTTPException(
                429, "This anonymous scan has reached its configured agent-task limit"
            )
        requested = data.runs or (1 if legacy else policy["default_runs"])
        if requested > policy["runs_limit"]:
            raise HTTPException(422, "Requested repeats exceed this scan's configured run limit")
        if not automatic:
            consume_admission(self.session, identity, "task", settings)
        start = AgentScope(scan.project.website_url, []).accept(scan.project.website_url)
        now = datetime.now(UTC)
        task = AgentTaskTest(
            scan_id=scan_id,
            task_type=data.task_type,
            task_description=TASKS[data.task_type],
            requested_runs=requested,
            status=ScanStatus.PENDING,
            policy_snapshot=policy,
            deadline=now
            + timedelta(
                seconds=settings.scan_queue_wait
                + min(settings.agent_stage_duration, requested * policy["duration_seconds"] + 20)
            ),
        )
        self.session.add(task)
        self.session.flush()
        for number in range(1, requested + 1):
            self.session.add(
                WorkflowTest(
                    scan_id=scan_id,
                    task_test_id=task.id,
                    run_number=number,
                    task_name=data.task_type,
                    task_type=data.task_type,
                    task_description=task.task_description,
                    starting_url=start,
                    allowed_domains=[],
                    model_identifier=policy["model_identifier"],
                    status=WorkflowStatus.PENDING,
                    execution_deadline=task.deadline,
                )
            )
        self.session.commit()
        return task

    def create(self, scan_id: UUID, data: AgentTestCreate, identity="local"):
        if data.allowed_domains:
            raise HTTPException(
                422,
                "Agent tasks stay on the scanned hostname; additional domains are not permitted",
            )
        task = self.create_task(
            scan_id, AgentTaskCreate(task_type=data.task_type, runs=1), identity, legacy=True
        )
        return self.records.runs(task.id, 1, 0)[0]


def runtime_settings(settings, policy):
    return settings.model_copy(
        update={
            "agent_model": policy.get("model_identifier", settings.agent_model),
            "agent_max_steps": policy.get("max_steps", settings.agent_max_steps),
            "agent_duration": policy.get("duration_seconds", settings.agent_duration),
            "agent_token_budget": policy.get("token_budget", settings.agent_token_budget),
            "agent_action_delay": max(1, policy.get("action_delay", settings.agent_action_delay)),
            "agent_judge_enabled": policy.get("judge_enabled", settings.agent_judge_enabled),
            "agent_input_cost_per_million": policy.get("cost_rates", {}).get(
                "input", settings.agent_input_cost_per_million
            ),
            "agent_output_cost_per_million": policy.get("cost_rates", {}).get(
                "output", settings.agent_output_cost_per_million
            ),
        }
    )


def execute_agent_test(
    test_id: UUID,
    session_factory=SessionLocal,
    browser_factory=BrowserSession,
    provider_factory=get_agent_provider,
):
    """Compatibility endpoint: new executions are owned by a bounded parent task."""
    with session_factory() as session:
        test = AgentRecords(session).test(test_id)
        parent = test.task_test_id if test else None
    if parent:
        execute_agent_task(parent, session_factory, browser_factory, provider_factory)
    else:
        asyncio.run(_execute_run(test_id, session_factory, browser_factory, provider_factory))


def execute_agent_task(
    task_id: UUID,
    session_factory=SessionLocal,
    browser_factory=BrowserSession,
    provider_factory=get_agent_provider,
):
    asyncio.run(run_agent_task(task_id, session_factory, browser_factory, provider_factory))


async def run_agent_task(
    task_id,
    session_factory=SessionLocal,
    browser_factory=BrowserSession,
    provider_factory=get_agent_provider,
):
    settings = get_settings()
    claimed = False
    try:
        with session_factory() as session:
            Records(session).admission_lock()
            running = session.scalar(
                select(func.count())
                .select_from(AgentTaskTest)
                .where(AgentTaskTest.status == ScanStatus.RUNNING)
            )
            if running >= settings.agent_max_active:
                session.rollback()
                return False
            records = AgentRecords(session)
            task = records.task(task_id)
            if not task:
                return False
            policy = dict(task.policy_snapshot)
            budget = min(
                settings.agent_stage_duration,
                task.requested_runs * policy.get("duration_seconds", settings.agent_duration) + 20,
            )
            if not records.claim_task(task_id, datetime.now(UTC) + timedelta(seconds=budget + 15)):
                session.rollback()
                return False
            claimed = True
            run_ids = [run.id for run in records.runs(task_id, 3, 0)]
            session.commit()
        async with asyncio.timeout(budget):
            for run_id in run_ids:
                await _execute_run(
                    run_id, session_factory, browser_factory, provider_factory, policy
                )
                update_task(task_id, session_factory)
        update_task(task_id, session_factory, terminal=True)
        return True
    except (Exception, asyncio.CancelledError) as exc:
        if claimed:
            logger.error(
                "agent_task_interrupted",
                extra={"task_id": str(task_id), "error_type": type(exc).__name__},
            )
            fail_task_pending_runs(
                task_id,
                "Agent task infrastructure interrupted; completed evidence was retained",
                session_factory,
            )
            update_task(task_id, session_factory, terminal=True)
        if isinstance(exc, asyncio.CancelledError):
            raise
        return False


async def _execute_run(test_id, session_factory, browser_factory, provider_factory, policy=None):
    runner = provider = browser = None
    started = time.monotonic()
    try:
        with session_factory() as session:
            records = AgentRecords(session)
            if not records.claim(test_id):
                session.rollback()
                return
            test = records.test(test_id)
            if not test:
                return
            if test.task_test_id:
                parent = records.task(test.task_test_id)
                if not parent or test.run_number > parent.requested_runs:
                    raise RuntimeError("Run exceeds its parent task policy")
            settings = runtime_settings(get_settings(), policy or {})
            test.execution_deadline = datetime.now(UTC) + timedelta(
                seconds=settings.agent_duration + 15
            )
            test.model_identifier = settings.agent_model
            url, task_type, goal = test.starting_url, test.task_type, test.task_description
            session.commit()
        provider = provider_factory(settings)
        browser = browser_factory(url, [], settings, str(test_id))
        runner = AgentRunner(browser, provider, settings)
        event("agent_test_started", test_id=str(test_id), model=settings.agent_model)

        def persist(data):
            with session_factory() as session:
                test = AgentRecords(session).test(test_id)
                if test is None or test.status != WorkflowStatus.RUNNING:
                    raise RuntimeError("Agent run is no longer running")
                clean = sanitize(data)
                session.add(AgentStep(workflow_test_id=test_id, **clean))
                test.steps_completed = clean["step_number"]
                test.final_url = clean["page_url"]
                test.metrics = sanitize(dict(runner.metrics))
                session.commit()

        result = await runner.run(goal, url, persist, task_type=task_type)
        finalize_run(test_id, result, session_factory)
        event(
            "agent_test_completed",
            test_id=str(test_id),
            steps=result.steps_completed,
            duration_seconds=round(result.execution_duration, 3),
            outcome=result.outcome,
        )
    except (Exception, asyncio.CancelledError) as exc:
        logger.error(
            "agent_test_infrastructure_error",
            extra={"test_id": str(test_id), "error_type": type(exc).__name__},
        )
        reason = (
            redact(str(exc), 400)
            if isinstance(exc, InferenceError)
            else f"Agent execution infrastructure unavailable ({type(exc).__name__})"
        )
        result = RunResult(
            outcome="UNAVAILABLE",
            failure_category="infra_error",
            failure_reason=reason,
            execution_duration=time.monotonic() - started,
            model_identifier=get_settings().agent_model,
        )
        finalize_run(test_id, result, session_factory)
        if isinstance(exc, asyncio.CancelledError):
            raise
    finally:
        # Runner closes both resources once entered. Also cover constructor failures.
        if runner is None:
            if browser:
                await browser.close()
            if provider:
                await provider.close()


def finalize_run(test_id, result: RunResult, session_factory):
    try:
        with session_factory() as session:
            test = AgentRecords(session).test(test_id)
            if not test or test.status != WorkflowStatus.RUNNING:
                return
            test.status = (
                WorkflowStatus.FAILED
                if result.outcome in ("FAILED", "UNAVAILABLE")
                else WorkflowStatus.COMPLETED
            )
            test.outcome = result.outcome
            test.verification_method = result.verification_method
            test.verification_evidence = sanitize(result.verification_evidence)
            test.failure_category = result.failure_category
            test.failure_reason = (
                redact(result.failure_reason, 500) if result.failure_reason else None
            )
            test.agent_declared_outcome = (
                redact(result.agent_declared_outcome, 2000)
                if result.agent_declared_outcome
                else None
            )
            test.steps_completed = result.steps_completed
            test.execution_duration = result.execution_duration
            test.final_url = public_url(result.final_url) if result.final_url else test.final_url
            test.prompt_tokens = result.prompt_tokens
            test.completion_tokens = result.completion_tokens
            test.estimated_cost_usd = result.estimated_cost_usd
            test.metrics = sanitize(result.metrics)
            test.completed_at = datetime.now(UTC)
            if result.model_identifier:
                test.model_identifier = result.model_identifier
            session.commit()
    except SQLAlchemyError:
        logger.error("agent_test_finalization_unavailable", extra={"test_id": str(test_id)})


def update_task(task_id, session_factory, terminal=False):
    with session_factory() as session:
        records = AgentRecords(session)
        task = records.task(task_id)
        if not task:
            return
        runs = records.runs(task_id, 3, 0)
        result = aggregate(runs)
        task.runs_completed = result["runs_completed"]
        task.eligible_runs = result["eligible_runs"]
        if terminal or result["runs_completed"] >= task.requested_runs:
            task.outcome = result["outcome"]
            task.consistency = result["consistency"]
            task.status = ScanStatus.COMPLETED
            task.completed_at = datetime.now(UTC)
            if not result["eligible_runs"]:
                task.failure_reason = next(
                    (run.failure_reason for run in runs if run.failure_reason),
                    "No conclusive task result is available",
                )
        else:
            # Partial repeats are progress, not a prematurely reported majority.
            task.outcome = None
            task.consistency = None
            task.status = ScanStatus.RUNNING
        session.commit()
        scan_id = task.scan_id
    refresh_agent_score(scan_id, session_factory)


def fail_task_pending_runs(task_id, reason, session_factory):
    with session_factory() as session:
        for run in AgentRecords(session).runs(task_id, 3, 0):
            if run.status in (WorkflowStatus.PENDING, WorkflowStatus.RUNNING):
                run.status, run.outcome, run.failure_category = (
                    WorkflowStatus.FAILED,
                    "UNAVAILABLE",
                    "infra_error",
                )
                run.failure_reason, run.completed_at = reason, datetime.now(UTC)
        session.commit()


def refresh_agent_score(scan_id, session_factory=SessionLocal):
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        if not scan:
            return
        tasks = list(
            session.scalars(
                select(AgentTaskTest)
                .where(AgentTaskTest.scan_id == scan_id)
                .order_by(AgentTaskTest.created_at, AgentTaskTest.id)
            )
        )
        entries = [(task, AgentRecords(session).runs(task.id, 3, 0)) for task in tasks]
        summary = dict(scan.audit_summary)
        static_score = summary.get("static_score", summary.get("score", scan.overall_score))
        policy = summary.get("agent_policy") or snapshot(get_settings())
        component = blend(static_score, entries, policy["score_weight"])
        summary.update(
            static_score=static_score,
            score_kind=component["score_kind"],
            score=component["score"],
            agent=component,
        )
        summary["provisional"] = bool(summary.get("provisional") or component["provisional"])
        scan.audit_summary = summary
        scan.overall_score = component["score"]
        session.commit()
    # Finding mapper is isolated from score math and can be called after each run.
    from app.services.agent_findings import sync_agent_findings

    sync_agent_findings(scan_id, session_factory)


async def run_scan_agent_stage(
    scan_id,
    settings,
    session_factory=SessionLocal,
    browser_factory=BrowserSession,
    provider_factory=get_agent_provider,
):
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        policy = dict(scan.audit_summary.get("agent_policy") or snapshot(settings))
        scan.audit_summary = {
            **scan.audit_summary,
            "agent_policy": policy,
            "static_score": scan.audit_summary.get("static_score", scan.overall_score),
            "phase": "AGENT_TASKS",
        }
        scan.execution_deadline = datetime.now(UTC) + timedelta(
            seconds=policy["stage_seconds"] + 20
        )
        session.commit()
    if not policy["pipeline_enabled"]:
        refresh_agent_score(scan_id, session_factory)
        with session_factory() as session:
            scan = session.get(Scan, scan_id)
            if scan:
                summary = dict(scan.audit_summary)
                reason = "Agent task execution is disabled by the operator; using the static score."
                component = dict(summary.get("agent") or {})
                component["fallback_reason"] = reason
                summary["agent"] = component
                summary["agent_stage"] = {
                    "status": "SKIPPED",
                    "reason": reason,
                }
                scan.audit_summary = summary
                session.commit()
        return
    stage_error = None
    try:
        async with asyncio.timeout(policy["stage_seconds"]):
            for task_type in policy["task_types"]:
                with session_factory() as session:
                    task = AgentService(session).create_task(
                        scan_id,
                        AgentTaskCreate(task_type=task_type, runs=policy["default_runs"]),
                        automatic=True,
                    )
                    task_id = task.id
                while True:
                    executed = await run_agent_task(
                        task_id, session_factory, browser_factory, provider_factory
                    )
                    with session_factory() as session:
                        state = AgentRecords(session).task(task_id)
                        done = state.status not in ACTIVE
                    if executed or done:
                        break
                    await asyncio.sleep(1)
    except (Exception, asyncio.CancelledError) as exc:  # noqa: BLE001 - preserve static report on any agent-stage fault
        logger.error(
            "agent_stage_unavailable",
            extra={"scan_id": str(scan_id), "error_type": type(exc).__name__},
        )
        stage_error = "Agent tests were unavailable or the separate agent-stage budget expired. Static results were retained."
        with session_factory() as session:
            ids = list(
                session.scalars(
                    select(AgentTaskTest.id).where(
                        AgentTaskTest.scan_id == scan_id, AgentTaskTest.status.in_(ACTIVE)
                    )
                )
            )
        for task_id in ids:
            fail_task_pending_runs(
                task_id,
                "Agent stage unavailable or its separate execution budget expired",
                session_factory,
            )
            update_task(task_id, session_factory, terminal=True)
        if isinstance(exc, asyncio.CancelledError):
            # Stage cancellation must not turn a completed static audit into a site failure.
            refresh_agent_score(scan_id, session_factory)
            return
    refresh_agent_score(scan_id, session_factory)
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        if scan:
            summary = dict(scan.audit_summary)
            component = summary.get("agent", {})
            if stage_error:
                component["fallback_reason"] = stage_error
                component["provisional"] = True
                summary["agent"] = component
            unavailable_only = (
                component.get("agent_score") is None and component.get("excluded_infra_runs", 0) > 0
            )
            summary["agent_stage"] = {
                "status": "UNAVAILABLE" if stage_error or unavailable_only else "COMPLETED",
                "reason": stage_error or component.get("fallback_reason"),
                "tasks_completed": sum(
                    entry.get("runs_completed", 0) > 0 for entry in component.get("tasks", [])
                ),
            }
            scan.audit_summary = summary
            session.commit()
