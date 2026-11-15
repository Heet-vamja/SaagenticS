"""Customer fix loop, scoped to an expiring report capability. No inference."""

import hashlib
import io
import json
import zipfile

from fastapi import HTTPException

from app.engines.agent.privacy import public_url, redact
from app.engines.fixes.assets import generate_assets
from app.engines.fixes.prompts import TEMPLATE, generate_prompts, prompt_batches
from app.engines.static_audit.checks import normalize_access_check
from app.models.domain import Scan, ScanStatus
from app.repositories.fixes import FixRecords
from app.schemas.fixes import (
    CustomerFix,
    FixCenterRead,
    FixComparison,
    FixVerification,
    FreeFixPreview,
)
from app.services.audits import AuditService, RecordNotFound
from app.services.free_reports import _evidence_summary, score_summary
from app.services.reports import SEVERITY, ReportService

MAX_FIXES = 100


def check_key(check):
    evidence = check.get("evidence") or {}
    identity = (
        check.get("rule"),
        evidence.get("page_key") or public_url(str(check.get("url") or "")),
    )
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]


def indexed_checks(scan):
    result = {}
    # Unknown or failed duplicate measurements must not be overwritten by a pass.
    priority = {"FAIL": 5, "UNKNOWN": 4, "PASS": 3, "NOT_APPLICABLE": 2, "INFO": 1}
    for check in (scan.audit_summary or {}).get("checks", [])[:10000]:
        if not isinstance(check, dict) or check.get("status") not in priority:
            continue
        check = normalize_access_check(check)
        key = check_key(check)
        if key not in result or priority[check["status"]] > priority[result[key]["status"]]:
            result[key] = check
    return result


def compare_fixes(before, after):
    old_rows = [
        (key, check) for key, check in indexed_checks(before).items() if check["status"] == "FAIL"
    ]
    old_rows.sort(
        key=lambda item: (
            -SEVERITY.get(item[1].get("severity"), 0),
            str(item[1].get("rule")),
            str(item[1].get("url")),
        )
    )
    old = dict(old_rows[:MAX_FIXES])
    usable = (
        before.id != after.id
        and before.project_id == after.project_id
        and before.status == after.status == ScanStatus.COMPLETED
        and bool((before.audit_summary or {}).get("version"))
        and before.audit_summary["version"] == (after.audit_summary or {}).get("version")
    )
    if before.completed_at and after.started_at and after.started_at < before.completed_at:
        usable = False
    current = indexed_checks(after)
    results = []
    for key, check in old.items():
        state = current.get(key, {}).get("status") if usable else None
        status = (
            "VERIFIED_FIXED"
            if state == "PASS"
            else "STILL_FAILING"
            if state == "FAIL"
            else "NOT_RETESTED"
        )
        results.append(
            FixVerification(
                key=key,
                title=redact(str(check.get("title") or "Website issue"), 300),
                url=public_url(str(check["url"])) if check.get("url") else None,
                status=status,
            )
        )
    before_score, _, a = score_summary(before.audit_summary or {})
    after_score, _, b = score_summary(after.audit_summary or {})
    score_comparable = (
        usable
        and set(indexed_checks(before)) == set(current)
        and a.evaluated == b.evaluated
        and a.total == b.total
    )
    return FixComparison(
        available=usable,
        reason=None
        if usable
        else "Both linked scans must finish with the same audit rubric and the rescan must run after the baseline. Missing or unknown checks are never confirmed fixed.",
        confirmed=sum(item.status == "VERIFIED_FIXED" for item in results),
        total=len(results),
        results=results,
        score_before=before_score if usable else None,
        score_after=after_score if usable else None,
        score_delta=round(after_score - before_score, 1)
        if score_comparable and before_score is not None and after_score is not None
        else None,
    )


class CustomerFixService:
    def __init__(self, session, token):
        self.session = session
        self.reports = ReportService(session)
        self.share = self.reports.shared_link(token)
        self.audits = AuditService(session)
        self.scan = self.audits.scan(self.share.scan_id)
        if (self.scan.audit_summary or {}).get("scan_mode") != "FREE_REPORT":
            raise RecordNotFound("Report link not found or expired")
        self.records = FixRecords(session)

    def center(self, robots_preset="keep_existing"):
        if self.scan.status in {ScanStatus.PENDING, ScanStatus.RUNNING}:
            raise HTTPException(409, "Wait for the scan to finish before generating fix guidance")
        events = self.records.events(self.share.id)
        by_key = {}
        for event in events:
            by_key.setdefault(event.fix_key, set()).add(event.event_type)
        comparison = FixComparison(
            available=False,
            reason="Apply a fix, then use Re-scan to verify to compare against this report.",
        )
        if self.share.baseline_scan_id:
            before = self.session.get(Scan, self.share.baseline_scan_id)
            if (
                before
                and before.project_id == self.scan.project_id
                and (before.audit_summary or {}).get("scan_mode") == "FREE_REPORT"
            ):
                comparison = compare_fixes(before, self.scan)
        comparison_status = {result.key: result.status for result in comparison.results}
        checks = [
            check for check in indexed_checks(self.scan).values() if check["status"] == "FAIL"
        ]
        checks.sort(
            key=lambda check: (
                -SEVERITY.get(check.get("severity"), 0),
                str(check.get("rule")),
                str(check.get("url")),
            )
        )
        fixes = []
        for check in checks[:MAX_FIXES]:
            key = check_key(check)
            tracked = by_key.get(key, set())
            status = (
                "FIX_APPLIED"
                if "FIX_APPLIED" in tracked
                else "PROMPT_COPIED"
                if "PROMPT_COPIED" in tracked
                else "OPEN"
            )
            if comparison_status.get(key) == "STILL_FAILING" and "FIX_APPLIED" not in tracked:
                status = "STILL_FAILING"
            evidence = (
                _evidence_summary(check.get("evidence") or {}, "FAIL")
                or "Review the affected page and the recorded check result."
            )
            fixes.append(
                CustomerFix(
                    key=key,
                    title=redact(str(check.get("title") or "Website issue"), 300),
                    category=str(check.get("bucket") or "Website readiness"),
                    severity=str(check.get("severity") or "MEDIUM"),
                    url=public_url(str(check["url"])) if check.get("url") else None,
                    evidence=redact(evidence, 1400),
                    recommendation=redact(
                        str(
                            check.get("recommendation")
                            or "Review the observed issue in context before editing."
                        ),
                        1200,
                    ),
                    template_version=TEMPLATE["version"],
                    prompts=generate_prompts(check, evidence),
                    status=status,
                )
            )
        project = self.audits.project(self.scan.project_id)
        pages = self.audits.records.pages(self.scan.id, 100, 0)
        assets, missing = generate_assets(pages, project.website_url, robots_preset)
        return FixCenterRead(
            version="customer-fixes-v1",
            fixes=fixes,
            truncated=len(checks) > MAX_FIXES,
            assets=assets,
            missing_information=missing,
            comparison=comparison,
            events=sorted(by_key.get("", set())),
        )

    def preview(self):
        """Three usable samples; never return the rest of the kit to a free client."""
        center = self.center("keep_existing")
        distinct = {}
        for fix in center.fixes:
            distinct.setdefault((fix.category, fix.title), fix)
        fixes = list(distinct.values())
        selected = fixes[:3]
        assets = [asset for asset in center.assets if asset.validated]
        selected_assets = assets[: 3 - len(selected)]
        return FreeFixPreview(
            fixes=selected,
            assets=selected_assets,
            remaining_fixes=len(fixes) - len(selected),
            remaining_assets=len(assets) - len(selected_assets),
            truncated=center.truncated,
        )

    def record(self, event_type, key="", robots_preset="keep_existing"):
        center = self.center(robots_preset)
        if event_type in {"PROMPT_COPIED", "FIX_APPLIED"}:
            if key not in {fix.key for fix in center.fixes}:
                raise RecordNotFound("Finding not available in this report")
        elif event_type == "ASSET_DOWNLOADED":
            if key not in {asset.key for asset in center.assets}:
                raise RecordNotFound("Validated asset not available in this report")
        elif key:
            raise HTTPException(422, "This report-level event does not accept a finding key")
        opposite = {
            "USEFUL": "NOT_USEFUL",
            "NOT_USEFUL": "USEFUL",
            "PRICE_INTERESTED": "PRICE_NOT_INTERESTED",
            "PRICE_NOT_INTERESTED": "PRICE_INTERESTED",
        }
        if opposite.get(event_type) in center.events:
            raise HTTPException(409, "Feedback has already been recorded for this report")
        self.records.record(self.share.id, key, event_type)
        self.session.commit()
        return {"recorded": True}

    def rescan(self, identity):
        if self.scan.status in {ScanStatus.PENDING, ScanStatus.RUNNING}:
            raise HTTPException(409, "Wait for this scan to finish before starting a rescan")
        project = self.audits.project(self.scan.project_id)
        scan, token, expires = self.audits.create_free_scan(project.website_url, identity)
        share = self.reports.shared_link(token)
        share.baseline_scan_id = self.scan.id
        self.session.commit()
        return scan, {
            "report_path": f"/free-reports/{token}",
            "status": scan.status.value,
            "expires_at": expires,
        }

    def fix_pack(self, robots_preset="keep_existing"):
        center = self.center(robots_preset)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for asset in center.assets:
                archive.writestr(asset.filename, asset.content)
            for number, batch in enumerate(prompt_batches(center.fixes), 1):
                archive.writestr(f"fix-everything-{number:02d}.md", batch)
            archive.writestr("report-fixes.json", center.model_dump_json(indent=2))
            archive.writestr(
                "READ-ME.txt",
                "Review every change with the site owner before deployment.\n\n"
                + "\n\n".join(
                    f"{asset.filename}: {asset.placement}\nSource: {asset.provenance}"
                    for asset in center.assets
                )
                + "\n\nMissing information:\n"
                + "\n".join(center.missing_information)
                + "\n\nPrompts and assets are deterministic suggestions. They have not modified your site. Re-scan to confirm individual checks.\n",
            )
        return stream.getvalue()
