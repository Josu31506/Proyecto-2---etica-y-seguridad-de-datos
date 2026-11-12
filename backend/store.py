from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    MetaData,
    Table,
    Column as C,
    String as S,
    Integer as I,
    Boolean as B,
    Float,
    LargeBinary,
    ForeignKey as FK,
    CheckConstraint,
    create_engine,
    event,
    insert,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.schema import CreateSchema

meta = MetaData()
users = Table(
    "accounts",
    meta,
    C("id", S(80), primary_key=True),
    C("name", S(100), nullable=False),
    C("role", S(16), nullable=False),
    C("email", S(254), unique=True),
    C("password_hash", LargeBinary),
    C("trainer", S(80), FK("accounts.id")),
    C("analytics", B, nullable=False, default=False),
    C("consent_at", S(32)),
    C("consent_version", S(24)),
    C("source", S(16), nullable=False),
    CheckConstraint("role in ('cliente','entrenador','administrador')"),
)
sessions = Table(
    "sessions",
    meta,
    C("digest", S(64), primary_key=True),
    C("user_id", S(80), FK("accounts.id"), nullable=False),
    C("expires", I, nullable=False),
)
metrics = Table(
    "daily_metrics",
    meta,
    C("owner", S(80), FK("accounts.id"), primary_key=True),
    C("day", S(10), primary_key=True),
    C("version", S(40), nullable=False),
    C("blob", LargeBinary, nullable=False),
)
study_sources = Table(
    "study_sources",
    meta,
    C("name", S(30), primary_key=True),
)
research = Table(
    "study_daily",
    meta,
    C("owner", S(80), primary_key=True),
    C("day", S(10), primary_key=True),
    C("version", S(40), nullable=False),
    C("blob", LargeBinary, nullable=False),
)
plans = Table(
    "sessions_plan",
    meta,
    C("id", S(40), primary_key=True),
    C("owner", S(80), FK("accounts.id"), nullable=False),
    C("day", S(10), nullable=False),
    C("label", S(100), nullable=False),
    C("done", B, nullable=False, default=False),
    C("attended_at", S(32)),
    C("alert_at", S(32)),
)
audit = Table(
    "audit_events",
    meta,
    C("id", I, primary_key=True),
    C("at", S(32), nullable=False),
    C("actor", S(80), nullable=False),
    C("action", S(64), nullable=False),
    C("outcome", S(12), nullable=False),
)
ledger = Table(
    "dp_budget",
    meta,
    C("id", I, primary_key=True),
    C("spent", I, nullable=False),
    C("ceiling", I, nullable=False),
    CheckConstraint("spent >= 0 and spent <= ceiling"),
)
releases = Table(
    "dp_releases",
    meta,
    C("query_key", S(120), primary_key=True),
    C("created", S(32), nullable=False),
    C("answer", Float),
    C("epsilon_milli", I, nullable=False),
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid():
    return uuid4().hex


def record(c, actor, action, outcome="ok"):
    c.execute(
        insert(audit).values(at=now(), actor=actor, action=action, outcome=outcome)
    )


def upsert(c, table, values, keys, updates=None):
    stmt = (sqlite_insert if c.dialect.name == "sqlite" else pg_insert)(table).values(
        **values
    )
    if updates:
        stmt = stmt.on_conflict_do_update(
            index_elements=keys, set_={k: stmt.excluded[k] for k in updates}
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=keys)
    return c.execute(stmt)


def connect(settings):
    settings.directory.mkdir(parents=True, exist_ok=True)
    sqlite = settings.database.startswith("sqlite:")
    engine = create_engine(
        settings.database,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 20}
        if sqlite
        else {"options": "-csearch_path=alzace,pg_catalog"},
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def pragmas(dbapi, _):
            dbapi.execute("PRAGMA foreign_keys=ON")
            dbapi.execute("PRAGMA busy_timeout=20000")

    return engine


def initialize(engine):
    # Called by CLI/migration only, never creates a privileged account in hosted mode.
    with engine.begin() as c:
        if c.dialect.name == "postgresql":
            c.execute(CreateSchema("alzace", if_not_exists=True))
            c.exec_driver_sql("REVOKE ALL ON SCHEMA alzace FROM PUBLIC")
        meta.create_all(c)
        upsert(c, ledger, dict(id=1, spent=0, ceiling=2000), ["id"])
        if c.dialect.name == "sqlite":
            for op in ("UPDATE", "DELETE"):
                c.exec_driver_sql(
                    f"CREATE TRIGGER IF NOT EXISTS audit_no_{op} BEFORE {op} ON audit_events BEGIN SELECT RAISE(ABORT,'audit append only'); END"
                )
        else:
            c.exec_driver_sql(
                """CREATE OR REPLACE FUNCTION alzace.deny_audit_change() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit append only'; END $$"""
            )
            c.exec_driver_sql("DROP TRIGGER IF EXISTS audit_immutable ON audit_events")
            c.exec_driver_sql(
                "CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION alzace.deny_audit_change()"
            )
