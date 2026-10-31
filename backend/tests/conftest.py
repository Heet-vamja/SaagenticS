import asyncio
import os
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_session


@pytest.fixture
def session():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        pytest.fail("Set TEST_DATABASE_URL to a migrated disposable PostgreSQL database")
    test_engine = create_engine(url)
    with test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as db:
            yield db
        transaction.rollback()
    test_engine.dispose()


@pytest.fixture
def client(session, monkeypatch):
    from app.main import app

    # Integration tests explicitly drive mocked crawl execution in their own sessions.
    # Never start live website requests or a production database recovery task.
    monkeypatch.setattr("app.api.routes.execute_scan", AsyncMock())
    monkeypatch.setattr("app.api.agent_routes.execute_agent_test", AsyncMock())

    async def idle_recovery():
        await asyncio.Event().wait()

    monkeypatch.setattr("app.main.recover_expired_scans", idle_recovery)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
