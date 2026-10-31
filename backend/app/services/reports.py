"""Read-only reports, deterministic prioritization, coverage-aware comparison and sharing."""

import csv
import hashlib
import io
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.config import get_settings
from app.engines.agent.privacy import public_url, sanitize
from app.models.domain import (
    AgentStep,
    AgentTaskTest,
    Finding,
    ReportShare,
    Scan,
    ScanStatus,
    WorkflowTest,
)
from app.schemas.api import FindingRead, ProjectRead, ScanRead
from app.services.agent_evidence import evidence_ref
from app.services.audits import AuditService, RecordNotFound

SEVERITY = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1}


def rule_key(finding):
    return finding.evidence.get("rule", str(finding.id)).removeprefix("render.")


def page_key(finding):
    return finding.evidence.get("page_key") or finding.evidence.get("url", "site")


def rank(findings):
    affected = {}
    for finding in findings:
        affected.setdefault(rule_key(finding), set()).add(page_key(finding))
    return sorted(
        findings,
        key=lambda f: (
            -SEVERITY.get(f.severity.value, 0),
            -len(affected[rule_key(f)]),
            rule_key(f),
            (f.evidence.get("url") or ""),
            str(f.id),
        ),
    )


def priority_value(finding, findings):
    result = FindingRead.model_validate(finding).model_dump(mode="json")
    affected = [item for item in findings if rule_key(item) == rule_key(finding)]
    result["evidence"]["affected_pages"] = sorted(
        {(item.evidence.get("url") or "") for item in affected}
    )
    result["evidence"]["affected_page_count"] = len({page_key(item) for item in affected})
    return result


class ReportService:
    def __init__(self, session):
        self.session = session
        self.audits = AuditService(session)

    def report(self, scan_id: UUID, shared=False, share_token: str | None = None):
        scan = self.audits.scan(scan_id)
        project = self.audits.project(scan.project_id)
        findings = rank(
            list(self.session.scalars(select(Finding).where(Finding.scan_id == scan_id)))
        )
        priorities = []
        seen = set()
        for finding in findings:
            key = finding.evidence.get("rule", str(finding.id)).removeprefix("render.")
            if key not in seen:
                priorities.append(finding)
                seen.add(key)
            if len(priorities) == 5:
                break
        tasks = list(
            self.session.scalars(
                select(AgentTaskTest)
                .where(AgentTaskTest.scan_id == scan_id)
                .order_by(AgentTaskTest.created_at, AgentTaskTest.id)
            )
        )
        task_results = [self._task_report(task, shared, share_token) for task in tasks]
        agent = scan.audit_summary.get("agent")
        score_kind = scan.audit_summary.get("score_kind", "STATIC_READINESS")
        result = {
            "project": ProjectRead.model_validate(project).model_dump(mode="json"),
            "scan": ScanRead.model_validate(scan).model_dump(mode="json"),
            "score_kind": score_kind,
            "score_components": {
                "static_score": (agent or {}).get(
                    "static_score", scan.audit_summary.get("static_score")
                ),
                "agent_score": (agent or {}).get("agent_score"),
                "configured_weight": (agent or {}).get("configured_weight"),
                "effective_weight": (agent or {}).get("effective_weight"),
                "fallback_reason": (agent or {}).get("fallback_reason"),
                "eligible_runs": (agent or {}).get("eligible_runs", 0),
                "eligible_tasks": (agent or {}).get("eligible_tasks", 0),
                "excluded_infra_runs": (agent or {}).get("excluded_infra_runs", 0),
                "inconclusive_runs": (agent or {}).get("inconclusive_runs", 0),
                "incomplete_tasks": (agent or {}).get("incomplete_tasks", 0),
                "judged_runs": (agent or {}).get("judged_runs", 0),
                "provisional": (agent or {}).get("provisional", False),
            },
            "agent_tasks": task_results,
            "rubric": scan.audit_summary.get("version"),
            "audited": bool(scan.audit_summary.get("version")),
            "findings": [FindingRead.model_validate(f).model_dump(mode="json") for f in findings],
            "priority_fixes": [priority_value(f, findings) for f in priorities],
            "verification": "AGENT_RESULTS_REPORTED"
            if task_results
            else "AGENT_TASK_SUCCESS_NOT_EVALUATED",
            "sharing": "ANYONE_WITH_LINK" if shared else "WORKSPACE",
        }
        if shared:
            # Public report excludes task traces, screenshots, cookies, arbitrary
            # crawl metadata and query strings. No internal execution IDs are needed.
            result["project"] = {
                "name": project.name,
                "website_url": public_url(project.website_url),
            }
            result["scan"] = {
                "status": scan.status.value,
                "overall_score": scan.overall_score,
                "pages_discovered": scan.pages_discovered,
                "pages_crawled": scan.pages_crawled,
                "pages_failed": scan.pages_failed,
                "started_at": scan.started_at.isoformat() if scan.started_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                "audit_summary": self._public_summary(scan.audit_summary),
            }
            # The report-level aggregate is already an explicit safe projection.
            result["agent_tasks"] = task_results
            for collection in (result["findings"], result["priority_fixes"]):
                for finding in collection:
                    finding["id"] = hashlib.sha256(
                        (
                            finding["evidence"].get("rule", "")
                            + str(
                                finding["evidence"].get("page_key")
                                or finding["evidence"].get("url", "")
                            )
                        ).encode()
                    ).hexdigest()[:20]
                    for key in ("scan_id", "page_id"):
                        finding.pop(key, None)
                    for key in ("run_ref", "step_ref"):
                        finding["evidence"].pop(key, None)
        if shared:

            def scrub(value):
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return public_url(value)
                if isinstance(value, dict):
                    return {key: scrub(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [scrub(item) for item in value]
                return value

            result = scrub(result)
        return sanitize(result)

    def _task_report(self, task, shared, share_token=None):
        runs = list(
            self.session.scalars(
                select(WorkflowTest)
                .where(WorkflowTest.task_test_id == task.id)
                .order_by(WorkflowTest.run_number)
            )
        )
        projected_runs = []
        for run in runs:
            evidence = self._verification_evidence(run.verification_evidence)
            steps = list(
                self.session.scalars(
                    select(AgentStep)
                    .where(AgentStep.workflow_test_id == run.id)
                    .order_by(AgentStep.step_number)
                )
            )
            projected_steps = []
            for step in steps:
                step_value = {
                    "step_number": step.step_number,
                    "page_url": public_url(step.page_url),
                    "action_type": step.action_type,
                    "reason": str(step.reasoning_summary or "")[:180],
                    "duration_ms": step.duration_ms,
                    "error_message": str(step.error_message)[:240] if step.error_message else None,
                    "has_screenshot": bool(step.screenshot_path),
                }
                if not shared:
                    step_value["id"] = str(step.id)
                    step_value["screenshot_url"] = (
                        f"/api/v1/agent-tests/{run.id}/steps/{step.id}/screenshot"
                        if step.screenshot_path
                        else None
                    )
                elif share_token and step.screenshot_path:
                    run_ref = evidence_ref(share_token, task.scan_id, "run", run.id)
                    step_ref = evidence_ref(share_token, task.scan_id, "step", step.id)
                    step_value["screenshot_url"] = (
                        f"/api/v1/shares/{share_token}/evidence/{run_ref}/{step_ref}.png"
                    )
                projected_steps.append(step_value)
            projected = {
                "run_number": run.run_number,
                "status": run.status.value,
                "outcome": run.outcome,
                "verification_method": run.verification_method,
                "failure_category": run.failure_category,
                "model": run.model_identifier,
                "steps": run.steps_completed,
                "duration_seconds": run.execution_duration,
                "prompt_tokens": run.prompt_tokens,
                "completion_tokens": run.completion_tokens,
                "estimated_cost_usd": run.estimated_cost_usd,
                "evidence": evidence,
                "final_url": public_url(run.final_url) if run.final_url else None,
                "step_details": projected_steps,
            }
            if not shared:
                projected["id"] = str(run.id)
            projected_runs.append(projected)
        result = {
            "task_type": task.task_type,
            "description": task.task_description,
            "status": task.status.value,
            "outcome": task.outcome,
            "consistency": task.consistency,
            "requested_runs": task.requested_runs,
            "runs_completed": task.runs_completed,
            "eligible_runs": task.eligible_runs,
            "runs": projected_runs,
        }
        if not shared:
            result["id"] = str(task.id)
        return result

    @staticmethod
    def _verification_evidence(evidence):
        """Return task evidence fields that are useful and safe to share."""
        allowed = {
            "url",
            "pricing_context",
            "prices",
            "contact_context",
            "public_email_count",
            "public_address_count",
            "public_phone_count",
            "signup_context",
            "documentation_context",
            "documentation_content",
            "challenge",
            "not_found",
            "requires_js",
        }
        safe = {key: value for key, value in evidence.items() if key in allowed}
        if isinstance(safe.get("prices"), list):
            safe["prices"] = [str(value)[:80] for value in safe["prices"][:15]]
        forms = evidence.get("forms")
        if isinstance(forms, list):
            field_count = sum(
                len(form.get("fields", []))
                for form in forms[:10]
                if isinstance(form, dict) and isinstance(form.get("fields", []), list)
            )
            safe["forms"] = [{"field_count": min(field_count, 300)}]
        if "url" in safe:
            safe["url"] = public_url(str(safe["url"]))
        return sanitize(safe)

    @staticmethod
    def _public_summary(summary):
        """Strip operational policy and any execution-level material from shares."""
        safe = {key: value for key, value in summary.items() if key != "agent_policy"}
        return sanitize(safe)

    def compare(self, scan_id, before=None):
        current = self.audits.scan(scan_id)
        if before:
            previous = self.audits.scan(before)
            if previous.project_id != current.project_id or previous.id == current.id:
                raise HTTPException(422, "Compare two different scans of the same project")
        else:
            previous = self.session.scalar(
                select(Scan)
                .where(
                    Scan.project_id == current.project_id,
                    Scan.id != current.id,
                    Scan.created_at < current.created_at,
                    Scan.status.in_([ScanStatus.COMPLETED, ScanStatus.FAILED]),
                )
                .order_by(Scan.created_at.desc(), Scan.id)
                .limit(1)
            )
        if not previous:
            return {
                "available": False,
                "reason": "No earlier scan is available",
                "before": None,
                "after": str(current.id),
            }
        a, b = previous.audit_summary, current.audit_summary
        if not a.get("version") or a.get("version") != b.get("version"):
            return {
                "available": False,
                "reason": "Both scans need the same static audit rubric; re-scan legacy results",
                "before": str(previous.id),
                "after": str(current.id),
            }
        if current.status in (ScanStatus.PENDING, ScanStatus.RUNNING):
            return {
                "available": False,
                "reason": "Wait for the current scan to finish",
                "before": str(previous.id),
                "after": str(current.id),
            }

        def indexed(summary):
            result = {}
            for check in summary.get("checks", []):
                key = (check["rule"], check.get("evidence", {}).get("page_key") or check.get("url"))
                # Several policy checks can share a rule; only scored failures
                # participate in issue comparisons, not informational bot policies.
                if check["status"] != "INFO":
                    result[key] = check
            return result

        old, new = indexed(a), indexed(b)
        added, resolved, unchanged, not_retested = [], [], [], []
        for key, item in new.items():
            if item["status"] == "FAIL":
                (unchanged if old.get(key, {}).get("status") == "FAIL" else added).append(item)
        for key, item in old.items():
            if item["status"] != "FAIL":
                continue
            state = new.get(key, {}).get("status")
            if state in ("PASS", "NOT_APPLICABLE"):
                resolved.append(item)
            elif state != "FAIL":
                not_retested.append(item)
        old_agent = a.get("agent") or {}
        new_agent = b.get("agent") or {}
        old_tasks = self._task_outcomes(previous.id)
        new_tasks = self._task_outcomes(current.id)
        old_basis = self._score_basis(previous, old_agent)
        new_basis = self._score_basis(current, new_agent)
        score_comparable = old_basis == new_basis
        delta = (
            round(current.overall_score - previous.overall_score, 1)
            if score_comparable
            and current.overall_score is not None
            and previous.overall_score is not None
            else None
        )
        agent_comparable = self._scored_task_types(old_agent) == self._scored_task_types(new_agent)
        task_changes = [
            {
                "task_type": task_type,
                "before": old_tasks.get(task_type, {}).get("outcome"),
                "after": new_tasks.get(task_type, {}).get("outcome"),
                "changed": old_tasks.get(task_type, {}).get("outcome")
                != new_tasks.get(task_type, {}).get("outcome"),
                "before_eligible_runs": old_tasks.get(task_type, {}).get("eligible_runs", 0),
                "after_eligible_runs": new_tasks.get(task_type, {}).get("eligible_runs", 0),
            }
            for task_type in sorted(set(old_tasks) | set(new_tasks))
        ]
        return sanitize(
            {
                "available": True,
                "before": str(previous.id),
                "after": str(current.id),
                "score_delta": delta,
                "score_components": {
                    "before": self._score_components(previous, old_agent),
                    "after": self._score_components(current, new_agent),
                    "static_delta": self._delta(
                        old_agent.get("static_score", a.get("static_score")),
                        new_agent.get("static_score", b.get("static_score")),
                    ),
                    "agent_delta": self._delta(
                        old_agent.get("agent_score"), new_agent.get("agent_score")
                    )
                    if agent_comparable
                    else None,
                    "score_comparable": score_comparable,
                },
                "agent_coverage_changed": self._coverage(old_agent) != self._coverage(new_agent),
                "agent_task_changes": task_changes,
                "added": added,
                "resolved": resolved,
                "unchanged": unchanged,
                "not_retested": not_retested,
                "coverage_changed": a.get("coverage") != b.get("coverage"),
                "note": "An absent or unknown check is not counted as fixed. Score changes may reflect changed coverage.",
            }
        )

    @staticmethod
    def _delta(before, after):
        return round(after - before, 1) if before is not None and after is not None else None

    @staticmethod
    def _score_components(scan, agent):
        summary = scan.audit_summary
        return {
            "score_kind": summary.get("score_kind", "STATIC_READINESS"),
            "static_score": agent.get("static_score", summary.get("static_score")),
            "agent_score": agent.get("agent_score"),
            "effective_weight": agent.get("effective_weight"),
            "fallback_reason": agent.get("fallback_reason"),
            "eligible_runs": agent.get("eligible_runs", 0),
            "excluded_infra_runs": agent.get("excluded_infra_runs", 0),
            "inconclusive_runs": agent.get("inconclusive_runs", 0),
            "judged_runs": agent.get("judged_runs", 0),
        }

    @staticmethod
    def _coverage(agent):
        return tuple(
            agent.get(key, 0)
            for key in (
                "eligible_runs",
                "eligible_tasks",
                "excluded_infra_runs",
                "inconclusive_runs",
                "incomplete_tasks",
                "judged_runs",
            )
        ) + (ReportService._scored_task_types(agent),)

    @staticmethod
    def _scored_task_types(agent):
        return tuple(
            sorted(
                task.get("task_type")
                for task in agent.get("tasks", [])
                if task.get("outcome") in ("SUCCEEDED", "FAILED")
            )
        )

    @staticmethod
    def _score_basis(scan, agent):
        summary = scan.audit_summary
        return (
            summary.get("score_kind", "STATIC_READINESS"),
            agent.get("effective_weight", 0),
            ReportService._scored_task_types(agent),
        )

    def _task_outcomes(self, scan_id):
        tasks = list(
            self.session.scalars(
                select(AgentTaskTest)
                .where(AgentTaskTest.scan_id == scan_id)
                .order_by(AgentTaskTest.created_at, AgentTaskTest.id)
            )
        )
        return {
            task.task_type: {
                "outcome": task.outcome,
                "eligible_runs": task.eligible_runs,
                "runs_completed": task.runs_completed,
                "consistency": task.consistency,
            }
            for task in tasks
        }

    def history(self, project_id, limit, offset):
        self.audits.project(project_id)
        return list(
            self.session.scalars(
                select(Scan)
                .where(Scan.project_id == project_id)
                .order_by(Scan.created_at.desc(), Scan.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def create_share(self, scan_id):
        scan = self.audits.scan(scan_id)
        if scan.status in (ScanStatus.PENDING, ScanStatus.RUNNING):
            raise HTTPException(409, "Wait for the scan to finish before sharing")
        token = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(days=get_settings().report_share_days)
        share = ReportShare(
            scan_id=scan_id,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=expires,
        )
        self.session.add(share)
        self.session.commit()
        return {
            "id": str(share.id),
            "path": "/reports/" + token,
            "expires_at": expires.isoformat(),
            "visibility": "ANYONE_WITH_LINK",
        }

    def shared_scan(self, token):
        if not 30 <= len(token) <= 100:
            raise RecordNotFound("Report link not found or expired")
        share = self.session.scalar(
            select(ReportShare).where(
                ReportShare.token_digest == hashlib.sha256(token.encode()).hexdigest(),
                ReportShare.revoked_at.is_(None),
                ReportShare.expires_at > datetime.now(UTC),
            )
        )
        if not share:
            raise RecordNotFound("Report link not found or expired")
        return share.scan_id

    def revoke_shares(self, scan_id):
        self.audits.scan(scan_id)
        self.session.execute(
            update(ReportShare)
            .where(ReportShare.scan_id == scan_id, ReportShare.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        self.session.commit()
        return {"revoked": True}


def csv_export(report):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        ["Severity", "Category", "Rule", "Page", "Issue", "Description", "Recommendation"]
    )

    def cell(value):
        text = str(value or "").replace("\x00", "")
        return (
            "'" + text
            if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@"))
            else text
        )

    for finding in report["findings"]:
        writer.writerow(
            [
                cell(v)
                for v in [
                    finding["severity"],
                    finding["category"],
                    finding["evidence"].get("rule"),
                    finding["evidence"].get("url"),
                    finding["title"],
                    finding["description"],
                    finding["recommendation"],
                ]
            ]
        )
    writer.writerow([])
    writer.writerow(
        [
            "Record Type",
            "Task",
            "Task Outcome",
            "Consistency",
            "Run",
            "Run Status",
            "Run Outcome",
            "Verification",
            "Failure Category",
            "Model",
            "Steps",
            "Duration Seconds",
            "Prompt Tokens",
            "Completion Tokens",
            "Estimated Cost USD",
            "Evidence URL",
            "Evidence Summary",
        ]
    )
    for task in report.get("agent_tasks", []):
        if not task.get("runs"):
            writer.writerow(
                [
                    cell(v)
                    for v in [
                        "task",
                        task.get("description"),
                        task.get("outcome"),
                        task.get("consistency"),
                    ]
                ]
            )
        for run in task.get("runs", []):
            evidence = run.get("evidence", {})
            summary = "; ".join(
                f"{key}={value}" for key, value in evidence.items() if key not in ("url", "title")
            )
            writer.writerow(
                [
                    cell(v)
                    for v in [
                        "agent_run",
                        task.get("description"),
                        task.get("outcome"),
                        task.get("consistency"),
                        run.get("run_number"),
                        run.get("status"),
                        run.get("outcome"),
                        run.get("verification_method"),
                        run.get("failure_category"),
                        run.get("model"),
                        run.get("steps"),
                        run.get("duration_seconds"),
                        run.get("prompt_tokens"),
                        run.get("completion_tokens"),
                        run.get("estimated_cost_usd"),
                        evidence.get("url"),
                        summary,
                    ]
                ]
            )
    return stream.getvalue().encode("utf-8-sig")
