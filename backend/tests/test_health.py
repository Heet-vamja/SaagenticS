import os

from sqlalchemy import create_engine

from app import main


def test_health_and_openapi(client, monkeypatch):
    test_engine = create_engine(os.environ["TEST_DATABASE_URL"])
    monkeypatch.setattr(main, "engine", test_engine)
    try:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok"}
        schema = client.get("/openapi.json").json()
        assert "/api/v1/projects" in schema["paths"]
        assert "/api/v1/scans/{scan_id}/findings" in schema["paths"]
        assert schema["paths"]["/api/v1/projects"]["post"]["responses"]["422"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/ErrorResponse")
        cors = client.options(
            "/api/v1/projects",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        assert cors.headers["access-control-allow-origin"] == "http://localhost:3000"
    finally:
        test_engine.dispose()
