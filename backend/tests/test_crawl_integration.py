from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.core.config import Settings
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator
from app.models.domain import Page, Project, Scan, ScanStatus
from app.repositories.records import Records
from app.services.crawls import execute_scan


def test_scan_execution_persistence_and_page_apis(client, session, monkeypatch):
    scheduled = []

    async def schedule(scan_id):
        scheduled.append(scan_id)

    monkeypatch.setattr("app.api.routes.execute_scan", schedule)
    project = client.post(
        "/api/v1/projects", json={"name": "Crawler", "website_url": "https://example.com"}
    ).json()
    response = client.post(f"/api/v1/projects/{project['id']}/scans")
    assert response.status_code == 201
    initial = response.json()
    assert initial["status"] == "PENDING"
    assert str(scheduled[0]) == initial["id"]
    assert initial["pages_crawled"] == 0

    @contextmanager
    def factory():
        yield session

    def crawler_factory(url, settings):
        def site(request):
            if request.url.path in ("/robots.txt", "/sitemap.xml"):
                return httpx.Response(404, stream=httpx.ByteStream(b""))
            body = b'<title>Saved title</title><meta name="description" content="Saved description"><a href="/missing">Missing</a>'
            status = 404 if request.url.path == "/missing" else 200
            return httpx.Response(
                status, headers={"content-type": "text/html"}, stream=httpx.ByteStream(body)
            )

        crawler = WebsiteCrawler(
            url, Settings(), Fetcher(URLValidator(url), Settings(), httpx.MockTransport(site))
        )
        original = crawler.crawl

        async def observed(persist, progress):
            session.expire_all()
            assert Records(session).scan(scheduled[0]).status == ScanStatus.RUNNING
            await original(persist, progress)

        crawler.crawl = observed
        return crawler

    execute_scan(scheduled[0], factory, crawler_factory)
    session.expire_all()
    scan = client.get(f"/api/v1/scans/{initial['id']}").json()
    assert scan["status"] == "COMPLETED"
    assert scan["pages_crawled"] == 2
    assert scan["pages_failed"] == 1
    assert scan["started_at"] and scan["completed_at"]
    assert 0 <= scan["overall_score"] <= 100
    assert scan["audit_summary"]["score_kind"] == "STATIC_READINESS"
    assert scan["audit_summary"]["counts"]["FAIL"] > 0
    pages = client.get(f"/api/v1/scans/{initial['id']}/pages?limit=1").json()
    assert len(pages) == 1
    assert pages[0]["title"] == "Saved title"
    assert pages[0]["meta_description"] == "Saved description"
    assert "html" not in pages[0]["page_metadata"]
    detail = client.get(f"/api/v1/scans/{initial['id']}/pages/{pages[0]['id']}")
    assert detail.json() == pages[0]
    assert len(client.get(f"/api/v1/scans/{initial['id']}/pages?offset=1").json()) == 1
    assert client.get(f"/api/v1/scans/{initial['id']}/pages/{uuid4()}").status_code == 404
    # A retried task cannot claim or duplicate a completed scan.
    execute_scan(scheduled[0], factory, crawler_factory)
    assert len(list(session.scalars(select(Page).where(Page.scan_id == scheduled[0])))) == 2
    other = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    assert client.get(f"/api/v1/scans/{other['id']}/pages/{pages[0]['id']}").status_code == 404
    assert client.get(f"/api/v1/scans/{uuid4()}/pages").status_code == 404
    assert client.get(f"/api/v1/scans/{initial['id']}/pages?limit=101").status_code == 422


def test_failures_and_deadline_recovery(session):
    project = Project(name="Failure", website_url="https://example.com/")
    session.add(project)
    session.flush()
    now = datetime.now(UTC)
    scan = Scan(project_id=project.id, execution_deadline=now + timedelta(seconds=100))
    expired = Scan(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        started_at=now - timedelta(minutes=10),
        execution_deadline=now - timedelta(seconds=1),
    )
    pending = Scan(project_id=project.id, execution_deadline=now - timedelta(seconds=1))
    session.add_all([scan, expired, pending])
    session.commit()

    @contextmanager
    def factory():
        yield session

    def broken(url, settings):
        raise ValueError("Invalid crawl scope")

    execute_scan(scan.id, factory, broken)
    session.expire_all()
    assert scan.status == ScanStatus.FAILED
    assert scan.error_summary == "Invalid crawl scope"
    assert scan.started_at and scan.completed_at
    Records(session).expire_scans()
    session.commit()
    session.expire_all()
    assert expired.status == pending.status == ScanStatus.FAILED
    assert pending.started_at and pending.completed_at
