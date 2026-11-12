from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from . import store as s
from .vault import decrypt

LIMA = timezone(timedelta(hours=-5))


def today():
    return datetime.now(LIMA).date()


def month_bounds(month):
    y, m = map(int, month.split("-"))
    return date(y, m, 1), date(y, m, monthrange(y, m)[1])


def periods():
    first = today().replace(day=1)
    months = []
    for _ in range(3):
        months.append(first.isoformat()[:7])
        first = (first - timedelta(days=1)).replace(day=1)
    return months


def due(day):
    return (
        (
            datetime.combine(
                date.fromisoformat(day) + timedelta(days=2),
                datetime.min.time(),
                tzinfo=LIMA,
            )
        )
        .astimezone(timezone.utc)
        .isoformat(timespec="seconds")
    )


def person_view(c, ring, owner):
    now = today()
    start = now.replace(day=1)
    week = (now - timedelta(days=now.weekday())).isoformat()
    rows = c.execute(
        select(s.metrics)
        .where(s.metrics.c.owner == owner)
        .order_by(s.metrics.c.day.desc())
        .limit(100)
    ).mappings()
    history = [{"day": r["day"], **decrypt(ring, s.metrics.name, r)} for r in rows]
    plans = (
        c.execute(
            select(s.plans)
            .where(s.plans.c.owner == owner)
            .order_by(s.plans.c.day.desc())
        )
        .mappings()
        .all()
    )
    sessions = [
        dict(
            id=p["id"],
            label=p["label"],
            day=p["day"],
            done=p["done"],
            attended=p["attended_at"],
            alert=(not p["done"] and due(p["day"]) <= s.now()),
        )
        for p in plans
    ]
    weekly = [
        p
        for p in sessions
        if week
        <= p["day"]
        <= (date.fromisoformat(week) + timedelta(days=6)).isoformat()
    ]
    return {
        "history": history,
        "plans": sessions,
        "weekly_done": sum(p["done"] for p in weekly),
        "weekly_total": len(weekly),
        "month_minutes": sum(
            r["minutes"] for r in history if r["day"] >= start.isoformat()
        ),
    }
