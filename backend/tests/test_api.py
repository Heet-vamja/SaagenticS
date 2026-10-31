from uuid import uuid4


def test_project_scan_vertical_slice(client):
    response = client.post(
        "/api/v1/projects", json={"name": "Example", "website_url": "https://example.com"}
    )
    assert response.status_code == 201
    project = response.json()
    assert project["website_url"] == "https://example.com/"
    assert client.get(f"/api/v1/projects/{project['id']}").json() == project
    assert project in client.get("/api/v1/projects").json()
    response = client.post("/api/v1/scans", json={"project_id": project["id"]})
    assert response.status_code == 201
    scan = response.json()
    assert scan["status"] == "PENDING"
    assert scan["overall_score"] is None
    assert scan["started_at"] is None
    assert scan["completed_at"] is None
    assert client.get(f"/api/v1/scans/{scan['id']}").json() == scan
    assert scan in client.get("/api/v1/scans").json()
    assert client.get(f"/api/v1/scans/{scan['id']}/findings").json() == []
    assert client.get(f"/api/v1/scans/{scan['id']}/workflow-tests").json() == []
    report = client.get(f"/api/v1/scans/{scan['id']}/report")
    assert report.status_code == 200
    assert report.json()["audited"] is False
    assert report.json()["score_kind"] == "STATIC_READINESS"


def test_missing_records_and_validation(client):
    missing = str(uuid4())
    for path in [
        f"/projects/{missing}",
        f"/scans/{missing}",
        f"/scans/{missing}/findings",
        f"/scans/{missing}/workflow-tests",
        f"/scans/{missing}/report",
    ]:
        response = client.get(f"/api/v1{path}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert client.post("/api/v1/scans", json={"project_id": missing}).status_code == 404
    for data in [
        {"name": " ", "website_url": "https://example.com"},
        {"name": "Name", "website_url": "ftp://example.com"},
        {"name": "Name", "website_url": "https://example.com", "unknown": True},
    ]:
        response = client.post("/api/v1/projects", json=data)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get("/api/v1/scans/not-a-uuid").status_code == 422
    assert client.get("/api/v1/projects?limit=101").status_code == 422
    assert client.get("/api/v1/projects?offset=-1").status_code == 422


def test_pagination(client):
    for name in ["One", "Two", "Three"]:
        assert (
            client.post(
                "/api/v1/projects", json={"name": name, "website_url": "https://example.com"}
            ).status_code
            == 201
        )
    first = client.get("/api/v1/projects?limit=2").json()
    second = client.get("/api/v1/projects?limit=2&offset=2").json()
    assert len(first) == 2
    assert len(second) == 1
    assert first[0]["id"] != second[0]["id"]
