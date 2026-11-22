"""Integration tests need a real PostgreSQL (docker compose up -d db) and these env vars:
   DATABASE_URL, ADMIN_API_KEY, TOKEN_SECRET.  They are skipped automatically if the DB is unreachable."""
import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("ADMIN_API_KEY", "test-admin"); os.environ.setdefault("TOKEN_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://govjobs:govjobs@localhost:5432/govjobs")

@pytest.fixture(scope="session")
def client():
    try:
        from sqlalchemy import text
        from app.db import engine
        with engine.connect() as c: c.execute(text("select 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL not reachable: {e}")
    from app import migrate; migrate.run()
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)

@pytest.fixture
def admin():
    return {"X-Admin-Key": os.environ["ADMIN_API_KEY"]}
