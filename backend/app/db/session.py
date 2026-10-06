from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def enable_sqlite_fks(engine) -> None:
    """SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked; PostgreSQL always enforces them."""
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


def make_engine(url: str | None = None):
    url = url or get_settings().database_url
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})
        enable_sqlite_fks(eng)
        return eng
    return create_engine(url, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
