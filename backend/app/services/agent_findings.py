"""Turn observed agent failures into idempotent, evidence-backed report findings."""

import hashlib

from sqlalchemy import delete, select

from app.engines.agent.privacy import public_url, redact
from app.models.domain import AgentStep, AgentTaskTest, Category, Finding, Scan, Severity
from app.repositories.agent_tests import AgentRecords

ENGINE = "agent-v1"

GUIDANCE = {
    "element_not_found": (
        Category.INTERACTABILITY,
        Severity.MEDIUM,
        "An agent could not find an expected control",
        "The task did not reach its target because the agent could not locate an expected interactive element.",
        "Give the control a clear visible label and accessible name, and keep the action available in the rendered page.",
    ),
    "blocked_by_captcha_or_bot_protection": (
        Category.RELIABILITY,
        Severity.HIGH,
        "A browser agent encountered an access challenge",
        "The read-only browser run encountered a visible access restriction and stopped without attempting to bypass it.",
        "Review the observed challenge and provide an intended, safe read-only path for public product information. Preserve protections on sensitive routes.",
    ),
    "content_requires_js": (
        Category.UNDERSTANDABILITY,
        Severity.MEDIUM,
        "Task information was not available to the browser agent",
        "The final page did not expose enough rendered text for the task to be verified.",
        "Render the relevant information in the page's accessible content and provide a clear loading or error state when it is unavailable.",
    ),
    "ambiguous_navigation": (
        Category.NAVIGABILITY,
        Severity.MEDIUM,
        "An agent could not determine the next navigation step",
        "The available page controls did not make the route to the requested information clear.",
        "Use descriptive link and button names that distinguish product, pricing, contact, and signup destinations.",
    ),
    "step_limit": (
        Category.NAVIGABILITY,
        Severity.LOW,
        "The requested task required too many navigation steps",
        "The bounded run ended before the task could be verified.",
        "Reduce unnecessary navigation steps and make key product information reachable from primary navigation.",
    ),
    "loop": (
        Category.NAVIGABILITY,
        Severity.MEDIUM,
        "An agent became stuck repeating a navigation action",
        "The same action at the same URL repeated without progress, so the run stopped safely.",
        "Ensure navigation controls lead to distinct destinations and show a clear state change after activation.",
    ),
    "malformed_output": (
        Category.RELIABILITY,
        Severity.INFO,
        "The agent could not interpret an action response",
        "The run stopped after the agent returned an action that failed structured validation; this may reflect model behavior rather than a website defect.",
        "Retry with the configured model after checking its availability and structured tool-call support. No website change is implied by this result.",
    ),
    "other": (
        Category.RELIABILITY,
        Severity.MEDIUM,
        "An agent task did not complete",
        "The browser task ended without the requested result being verified.",
        "Review the recorded page, action, and error evidence, then make the target route and content clear to a read-only browser agent.",
    ),
}


def sync_agent_findings(scan_id, session_factory):
    """Replace this scan's derived agent findings from persisted task evidence."""
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        if not scan:
            return
        session.execute(
            delete(Finding).where(
                Finding.scan_id == scan_id,
                Finding.evidence["engine"].as_string() == ENGINE,
            )
        )
        tasks = list(
            session.scalars(
                select(AgentTaskTest)
                .where(AgentTaskTest.scan_id == scan_id)
                .order_by(AgentTaskTest.created_at, AgentTaskTest.id)
            )
        )
        seen = set()
        for task in tasks:
            for run in AgentRecords(session).runs(task.id, 3, 0):
                category = run.failure_category
                # Provider, browser startup, timeout and network failures are not
                # evidence of a website defect and never become findings.
                if run.outcome != "FAILED" or category in (None, "infra_error"):
                    continue
                mapping = GUIDANCE.get(category, GUIDANCE["other"])
                step = None
                steps = list(
                    session.scalars(
                        select(AgentStep)
                        .where(AgentStep.workflow_test_id == run.id)
                        .order_by(AgentStep.step_number.desc())
                        .limit(1)
                    )
                )
                if steps:
                    step = steps[0]
                url = public_url(
                    (step.page_url if step else None) or run.final_url or run.starting_url
                )
                fingerprint = (task.task_type, category, url)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                category_value, severity, title, description, recommendation = mapping
                evidence = {
                    "engine": ENGINE,
                    "rule": f"agent.task.{task.task_type}.{category}",
                    "page_key": hashlib.sha256(url.encode()).hexdigest()[:20],
                    "failure_category": category,
                    "task_type": task.task_type,
                    "task_description": redact(task.task_description, 300),
                    "url": url,
                    "run_ref": str(run.id),
                    "verification_method": run.verification_method,
                    "reason": redact(run.failure_reason or "", 300),
                }
                if step:
                    evidence.update(
                        step_ref=str(step.id),
                        step_number=step.step_number,
                        action_type=step.action_type,
                        action_reason=redact(step.reasoning_summary, 180),
                        screenshot_available=bool(step.screenshot_path),
                    )
                session.add(
                    Finding(
                        scan_id=scan_id,
                        category=category_value,
                        severity=severity,
                        title=title,
                        description=description,
                        recommendation=recommendation,
                        confidence=0.55 if run.verification_method == "judged" else 0.75,
                        evidence=evidence,
                    )
                )
        session.commit()
