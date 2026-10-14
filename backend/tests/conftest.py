"""Set up a throwaway SQLite DB for backend tests.

The backend modules read ``DATABASE_URL``/``INGEST_API_KEY``/``JWT_SECRET_KEY``
at import time, so these must be present in the environment before any
``backend.*`` import happens.  ``mini_soc_config`` loads ``.env`` with
``override=False``, so the values below win.

The schema fixtures live here (not in the individual test modules) so the whole
backend test session shares one database and never races to delete it.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./backend-ci.db")
os.environ.setdefault("INGEST_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

# File behind the sqlite URL, so we can start each session from a clean slate.
DATABASE_FILE = os.environ["DATABASE_URL"].split("///")[-1]

import pytest  # noqa: E402

from backend.app.database import Base, engine, SessionLocal  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _fresh_schema():
    try:
        os.remove(DATABASE_FILE)
    except (FileNotFoundError, PermissionError):
        pass

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()
