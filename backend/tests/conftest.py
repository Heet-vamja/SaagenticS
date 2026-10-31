import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.main import app


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
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
