"""Database setup.

Default: SQLite file under data/. To switch to PostgreSQL, set the
DOCFLOW_DATABASE_URL environment variable, e.g.
    DOCFLOW_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/docflow
No other code changes are needed: all access goes through SQLModel sessions.
"""
import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DOCFLOW_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "DOCFLOW_DATABASE_URL", f"sqlite:///{DATA_DIR / 'docflow.db'}"
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
