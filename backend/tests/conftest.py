import os

os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["COOKIE_SECURE"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import rate_limit
from app.db.session import Base, enable_sqlite_fks, get_db
from app.main import app
from app.models import core  # noqa: F401  (registers tables)


@pytest.fixture()
def db_session():
    """In-memory SQLite by default. Set TEST_DATABASE_URL to a PostgreSQL URL (schema created by
    `alembic upgrade head`) to run the same suite against PostgreSQL; tables are truncated between tests."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        from sqlalchemy import text

        engine = create_engine(url, pool_pre_ping=True)
        Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        session = Session()
        yield session
        session.close()
        names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        engine.dispose()
        return
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    enable_sqlite_fks(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def override():
        yield db_session

    app.dependency_overrides[get_db] = override
    rate_limit.reset()
    rate_limit.ENABLED = True
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="a@example.com", password="correct-horse-1"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Test"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def freeze(monkeypatch):
    """Pin the application clock: freeze('2026-10-04T06:00:00+00:00'). Defaults to that instant."""
    from datetime import datetime, timezone

    from app.core import clock

    def _set(iso="2026-10-04T06:00:00+00:00"):
        dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
        monkeypatch.setattr(clock, "utcnow", lambda: dt)
        return dt

    _set()
    return _set
