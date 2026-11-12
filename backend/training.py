from datetime import date, timedelta
from sqlalchemy import select
from . import store as s
from .domain import month_bounds, today
from .vault import encrypt, decrypt

targets = s.Table(
    "targets",
    s.meta,
    s.C("owner", s.S(80), s.FK("accounts.id"), primary_key=True),
    s.C("day", s.S(10), primary_key=True),
    s.C("version", s.S(40), nullable=False),
    s.C("blob", s.LargeBinary, nullable=False),
)
members = s.Table(
    "memberships",
    s.meta,
    s.C("owner", s.S(80), s.FK("accounts.id"), primary_key=True),
    s.C("start", s.S(10), nullable=False),
    s.C("end", s.S(10)),
)


def save_target(c, ring, owner, start, config):
    enc = encrypt(ring, targets.name, owner, start, config)
    s.upsert(
        c,
        targets,
        dict(owner=owner, day=start, **enc),
        ["owner", "day"],
        ["version", "blob"],
    )


def default_targets(c, ring):
    anchor = today()
    start = anchor.replace(day=1).isoformat()
    for i, owner in enumerate(
        c.execute(
            select(s.users.c.id)
            .where(s.users.c.role == "cliente")
            .order_by(s.users.c.id)
        ).scalars()
    ):
        save_target(
            c,
            ring,
            owner,
            start,
            {"months": 1, "minutes": 750, "fat_drop": 0.8, "activity_weight": 0.6},
        )
        c.execute(
            members.insert().values(
                owner=owner,
                start=(anchor - timedelta(days=90)).isoformat(),
                end=(anchor.replace(day=1) - timedelta(days=7)).isoformat()
                if i % 9 == 0
                else None,
            )
        )


def progress(c, ring, owner, history):
    now = today()
    row = (
        c.execute(
            select(targets)
            .where(targets.c.owner == owner, targets.c.day <= now.isoformat())
            .order_by(targets.c.day.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    cfg = decrypt(ring, targets.name, row)
    a = date.fromisoformat(row["day"])
    year = a.year + (a.month - 1 + cfg["months"]) // 12
    end = date(year, (a.month - 1 + cfg["months"]) % 12 + 1, 1) - timedelta(days=1)
    if now > end:
        return None
    observed = [r for r in history if row["day"] <= r["day"] <= end.isoformat()]
    mins = sum(r["minutes"] for r in observed)
    fats = sorted((r["day"], r["fat"]) for r in observed if r.get("fat") is not None)
    fpart = (
        max(0, min(1, (fats[0][1] - fats[-1][1]) / cfg["fat_drop"]))
        if len(fats) >= 2
        else None
    )
    w = cfg["activity_weight"]
    total = (
        (100 * (w * min(1, mins / cfg["minutes"]) + (1 - w) * (fpart or 0)))
        if observed and (w == 1 or fpart is not None)
        else None
    )
    return {
        **cfg,
        "start": a.isoformat(),
        "end": end.isoformat(),
        "observed_minutes": mins,
        "percent": round(total) if total is not None else None,
    }


def operations(c):
    # Last CLOSED calendar month, not registrations or login counts.
    start, end = month_bounds(
        (today().replace(day=1) - timedelta(days=1)).isoformat()[:7]
    )
    cohort = c.execute(
        select(members).where(members.c.start <= start.isoformat())
    ).mappings()
    initial = [r for r in cohort if r["end"] is None or r["end"] >= start.isoformat()]
    retained = sum(r["end"] is None or r["end"] >= end.isoformat() for r in initial)
    return {
        "period": start.isoformat()[:7],
        "retention": round(retained * 100 / len(initial), 1) if initial else None,
    }
