"""Database bootstrap. The schema is created automatically at startup."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ..core.config import ROOT, get_config
from ..core.logging_conf import get_logger
from ..models.entities import Base

log = get_logger(__name__)

_engine = None
_SessionLocal = None


def _resolve_url(url: str) -> str:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url.replace("sqlite:///", "", 1)
        path = Path(rel)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"
    return url


def init_db(url: str | None = None):
    """Create the engine and every table. Safe to call repeatedly."""
    global _engine, _SessionLocal
    url = _resolve_url(url or get_config().get("database.url", "sqlite:///data/ais.db"))
    _engine = create_engine(url, future=True,
                            connect_args={"check_same_thread": False}
                            if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        with _engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    log.info("database initialised", extra={"event": "DB_INITIALISED"})
    return _engine


def get_engine():
    if _engine is None:
        init_db()
    return _engine


def SessionLocal():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


def healthy() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
