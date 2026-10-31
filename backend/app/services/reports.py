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
from app.models.domain import Finding, ReportShare, Scan, ScanStatus
from app.schemas.api import FindingRead, ProjectRead, ScanRead
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

    def report(self, scan_id: UUID, shared=False):
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
        result = {
            "project": ProjectRead.model_validate(project).model_dump(mode="json"),
            "scan": ScanRead.model_validate(scan).model_dump(mode="json"),
            "score_kind": "STATIC_READINESS",
            "rubric": scan.audit_summary.get("version"),
            "audited": bool(scan.audit_summary.get("version")),
            "findings": [FindingRead.model_validate(f).model_dump(mode="json") for f in findings],
            "priority_fixes": [priority_value(f, findings) for f in priorities],
            "verification": "AGENT_TASK_SUCCESS_NOT_EVALUATED",
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
                "audit_summary": scan.audit_summary,
            }
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
        delta = (
            round(current.overall_score - previous.overall_score, 1)
            if current.overall_score is not None and previous.overall_score is not None
            else None
        )
        return sanitize(
            {
                "available": True,
                "before": str(previous.id),
                "after": str(current.id),
                "score_delta": delta,
                "added": added,
                "resolved": resolved,
                "unchanged": unchanged,
                "not_retested": not_retested,
                "coverage_changed": a.get("coverage") != b.get("coverage"),
                "note": "An absent or unknown check is not counted as fixed. Score changes may reflect changed coverage.",
            }
        )

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
    return stream.getvalue().encode("utf-8-sig")
