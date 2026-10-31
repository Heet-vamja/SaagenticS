import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from app.models.domain import Category, Finding, Page, Project, Scan, Severity, WorkflowTest


def test_constraints_and_cascades(session):
    project = Project(name="Example", website_url="https://example.com/")
    session.add(project)
    session.flush()
    scan = Scan(project_id=project.id)
    other = Scan(project_id=project.id)
    session.add_all([scan, other])
    session.flush()
    page = Page(
        scan_id=scan.id, url="https://example.com/", page_metadata={"description": "Example"}
    )
    session.add(page)
    session.flush()
    finding = Finding(
        scan_id=scan.id,
        page_id=page.id,
        category=Category.DISCOVERABILITY,
        severity=Severity.LOW,
        title="Example finding",
        description="A test observation",
        confidence=0.8,
    )
    session.add(finding)
    session.flush()
    assert page.page_metadata["description"] == "Example"
    for invalid in [
        Scan(project_id=project.id, overall_score=101),
        Page(scan_id=scan.id, url="https://invalid.example/", status_code=999),
        WorkflowTest(
            scan_id=scan.id,
            task_name="Test",
            starting_url="https://example.com",
            execution_duration=-1,
        ),
        Finding(
            scan_id=other.id,
            page_id=page.id,
            category=Category.RELIABILITY,
            severity=Severity.HIGH,
            title="Cross scan",
            description="Must fail",
        ),
        Finding(
            scan_id=scan.id,
            category=Category.RELIABILITY,
            severity=Severity.HIGH,
            title="Confidence",
            description="Must fail",
            confidence=1.1,
        ),
    ]:
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(invalid)
            session.flush()
    scan_id, page_id, finding_id = scan.id, page.id, finding.id
    session.execute(delete(Project).where(Project.id == project.id))
    session.flush()
    session.expire_all()
    assert session.get(Scan, scan_id) is None
    assert session.get(Page, page_id) is None
    assert session.get(Finding, finding_id) is None
