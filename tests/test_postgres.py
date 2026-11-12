"""Integration on a dedicated, empty PostgreSQL test DB via ALZACE_TEST_PG."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import DBAPIError

from backend import store
from backend.cli import seed
from backend.config import Settings
from backend.domain import periods
from backend.service import release
from backend.vault import fresh


@pytest.mark.skipif(
    not os.environ.get("ALZACE_TEST_PG"), reason="Requiere PostgreSQL de pruebas vacío"
)
def test_postgresql_schema_audit_and_dp(tmp_path):
    dsn = os.environ["ALZACE_TEST_PG"]
    # Require an empty schema to keep the operator's existing data untouched.
    check = create_engine(dsn)
    with check.connect() as conn:
        if conn.execute(text("SELECT to_regnamespace('alzace')")).scalar():
            pytest.fail("Use una base de pruebas nueva y vacía.")
    check.dispose()
    engine = store.connect(Settings(tmp_path, dsn, "demo", "http://127.0.0.1"))
    ring = fresh()
    store.initialize(engine)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT current_schema()")).scalar() == "alzace"
        seed(conn, ring)

    def publish(_):
        with engine.begin() as conn:
            return release(
                conn, ring, {"id": "demo-administrador"}, "programa", periods()[0]
            )

    with ThreadPoolExecutor(4) as pool:
        answers = list(pool.map(publish, range(4)))
    assert sum(not result["cached"] for result in answers) == 1
    assert all(result["release"] == answers[0]["release"] for result in answers)
    with engine.connect() as conn:
        assert conn.execute(select(store.ledger.c.spent)).scalar_one() == 1000
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(update(store.audit).values(outcome="alterado"))
    engine.dispose()
