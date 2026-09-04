import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import DATABASE_URL
from app.core.database import get_db
from app.main import app

engine = create_engine(DATABASE_URL)


@pytest.fixture()
def db_session():
    """A session bound to a SAVEPOINT that's rolled back after each test.

    Runs against the same Postgres as dev (local Supabase CLI or cloud —
    whatever DATABASE_URL points at), so tests exercise the real schema
    (UUID/JSONB/pgvector types) without needing SQLite workarounds. Nothing
    written during a test is ever actually committed.
    """
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def current_user_override():
    """Bypass real JWKS verification — tests exercise our authorization
    logic (app/core/authorization.py, app/api/*), not Supabase's token
    issuance, which is already proven separately via manual end-to-end
    testing against real Supabase Auth."""

    def _set(user: dict):
        app.dependency_overrides[get_current_user] = lambda: user

    yield _set
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def alice():
    return {"id": str(uuid.uuid4()), "email": "alice@example.com"}


@pytest.fixture()
def bob():
    return {"id": str(uuid.uuid4()), "email": "bob@example.com"}
