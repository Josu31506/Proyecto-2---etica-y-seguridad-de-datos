"""Transactions for authorizations, immutable aggregate releases and controlled data use."""

from sqlalchemy import select, update
from fastapi import HTTPException
from . import store as s
from .privacy import contributions, private_mean, EPSILON, PERIODS
from .domain import periods, month_bounds
from .vault import decrypt


def check_access(c, actor, owner):
    person = (
        c.execute(
            select(s.users).where(s.users.c.id == owner, s.users.c.role == "cliente")
        )
        .mappings()
        .first()
    )
    if not person or not (
        actor["id"] == owner
        or (actor["role"] == "entrenador" and person["trainer"] == actor["id"])
    ):
        raise HTTPException(403, "Sin permiso para consultar este perfil.")
    return person


def public_user(u):
    return {k: u[k] for k in ("id", "name", "role", "analytics", "consent_at")}


def budget(c):
    row = c.execute(select(s.ledger).where(s.ledger.c.id == 1)).mappings().one()
    return {"spent": row["spent"] / 1000, "total": row["ceiling"] / 1000}


def describe(row):
    source, period = row["query_key"].split(":")[1:3]
    return {
        "source": source,
        "period": period,
        "minutes": row["answer"],
        "epsilon": row["epsilon_milli"] / 1000,
        "delta": 0,
        "created": row["created"],
    }


def release(c, ring, actor, source, month):
    if month not in (PERIODS if source == "estudio" else periods()):
        raise HTTPException(422, "Periodo no disponible.")
    key = f"mean-v1:{source}:{month}"
    # Same lock for *all* roles, queries, releases and processes. Works on SQLite and PostgreSQL.
    c.execute(update(s.ledger).where(s.ledger.c.id == 1).values(spent=s.ledger.c.spent))
    old = (
        c.execute(select(s.releases).where(s.releases.c.query_key == key))
        .mappings()
        .first()
    )
    if old:
        return {"release": describe(old), "cached": True, "budget": budget(c)}
    if (
        source == "estudio"
        and not c.execute(
            select(s.study_sources.c.name).where(s.study_sources.c.name == "fitbit")
        ).first()
    ):
        raise HTTPException(
            409,
            "Cargue el archivo del estudio antes de publicar. Puede usar el programa simulado.",
        )
    if (
        c.execute(
            update(s.ledger)
            .where(s.ledger.c.id == 1, s.ledger.c.spent + 1000 <= s.ledger.c.ceiling)
            .values(spent=s.ledger.c.spent + 1000)
        ).rowcount
        != 1
    ):
        raise HTTPException(
            409,
            "Se agotó el presupuesto compartido. Las publicaciones existentes siguen disponibles.",
        )
    lo, hi = month_bounds(month)
    table = s.research if source == "estudio" else s.metrics
    stmt = select(table).where(table.c.day.between(lo.isoformat(), hi.isoformat()))
    if table is s.metrics:
        stmt = stmt.join(s.users, s.users.c.id == table.c.owner).where(
            s.users.c.analytics.is_(True)
        )
    rows = c.execute(stmt).mappings()
    values = contributions(
        (r["owner"], r["day"], decrypt(ring, table.name, r)["minutes"]) for r in rows
    )
    answer = private_mean(values, EPSILON)
    item = dict(query_key=key, answer=answer, epsilon_milli=1000, created=s.now())
    c.execute(s.releases.insert().values(**item))
    s.record(c, actor["id"], "estadistica.publicar")
    return {"release": describe(item), "cached": False, "budget": budget(c)}
