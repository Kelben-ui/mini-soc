"""Set up a throwaway SQLite DB for backend tests.

The backend modules read ``DATABASE_URL``/``INGEST_API_KEY``/``JWT_SECRET_KEY``
at import time, so these must be present in the environment before any
``backend.*`` import happens.  ``mini_soc_config`` loads ``.env`` with
``override=False``, so the values below win.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./backend-ci.db")
os.environ.setdefault("INGEST_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")