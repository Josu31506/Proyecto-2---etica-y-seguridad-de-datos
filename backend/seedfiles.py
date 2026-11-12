"""Local-only paired, simulated clients from Fitbit summaries and shuffled Gym profiles."""

import argparse
import csv
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
import random
from statistics import fmean

from sqlalchemy import select, update

from . import store as s
from .cli import DEMO
from .config import Settings
from .dataio import read_activity
from .domain import today
from .training import save_target
from .vault import encrypt, pseudo, read_ring


def averages(path, column, ids, *, date_column=None):
    sums = defaultdict(float)
    counts = defaultdict(int)
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            subject = row["Id"]
            if subject not in ids or not row[column]:
                continue
            if date_column:
                day = (subject, row[date_column], row[column])
                if day in seen:
                    continue
                seen.add(day)
            sums[subject] += float(row[column])
            counts[subject] += 1
    return {subject: value / counts[subject] for subject, value in sums.items()}


def paired_profiles(fitbit_dir, gym_csv):
    daily, _ = read_activity([fitbit_dir / "dailyActivity_merged.csv"])
    histories = defaultdict(list)
    for (subject, _), value in daily.items():
        histories[subject].append(value)
    sleep = averages(
        fitbit_dir / "sleepDay_merged.csv",
        "TotalMinutesAsleep",
        histories,
        date_column="SleepDay",
    )
    pulse = averages(fitbit_dir / "heartrate_seconds_merged.csv", "Value", histories)
    weight = averages(
        fitbit_dir / "weightLogInfo_merged.csv",
        "WeightKg",
        histories,
        date_column="Date",
    )
    with gym_csv.open(encoding="utf-8-sig", newline="") as file:
        gym = list(csv.DictReader(file))
    if len(gym) < len(histories):
        raise ValueError("Se necesita al menos un perfil Gym por perfil simulado.")
    generator = random.Random(3031)
    generator.shuffle(gym)
    for (subject, records), body in zip(sorted(histories.items()), gym):
        yield (
            subject,
            {
                "minutes": round(fmean(v["minutes"] for v in records) / 10) * 10,
                "steps": round(fmean(v["steps"] for v in records) / 1000) * 1000,
                "fat": round(float(body["Fat_Percentage"]) / 3) * 3,
                "weight": round(weight.get(subject, float(body["Weight (kg)"])) / 5)
                * 5,
                "sleep": round(sleep[subject] / 30) * 30 if subject in sleep else None,
                "pulse": round(pulse[subject] / 10) * 10 if subject in pulse else None,
            },
        )


def load_paired(cfg, fitbit_dir, gym_csv):
    if cfg.mode != "demo":
        raise ValueError(
            "Los perfiles vinculados son exclusivos de la demostración local."
        )
    profiles = list(paired_profiles(fitbit_dir, gym_csv))
    ring = read_ring(cfg)
    engine = s.connect(cfg)
    added = 0
    anchor = today()
    try:
        with engine.begin() as c:
            # Serialize a retry or a second operator importing the same demo set.
            c.execute(
                update(s.ledger)
                .where(s.ledger.c.id == 1)
                .values(spent=s.ledger.c.spent)
            )
            if not c.execute(
                select(s.users.c.id).where(s.users.c.id == DEMO["entrenador"])
            ).first():
                raise ValueError("Primero hay que inicializar la demo.")
            for number, (subject, base) in enumerate(profiles, 1):
                owner = "sim-" + pseudo(ring, "paired:" + subject)[:32]
                if c.execute(select(s.users.c.id).where(s.users.c.id == owner)).first():
                    continue
                c.execute(
                    s.users.insert().values(
                        id=owner,
                        name=f"Perfil simulado {number:02}",
                        role="cliente",
                        source="demo_vinculado",
                        trainer=DEMO["entrenador"],
                        analytics=False,
                    )
                )
                # Generate a new series. No original dates or daily trajectories leave the ETL.
                rng = random.Random(owner)
                for days_ago in range(35):
                    day = (anchor - timedelta(days=days_ago)).isoformat()
                    values = {
                        "minutes": max(
                            0, min(1440, base["minutes"] + rng.randint(-12, 12))
                        ),
                        "steps": max(0, base["steps"] + rng.randint(-900, 900)),
                        "fat": round(
                            max(0, min(100, base["fat"] + rng.uniform(-0.4, 0.4))), 1
                        ),
                        "weight": round(max(1, base["weight"] + rng.uniform(-1, 1)), 1),
                        "sleep": max(0, min(1440, base["sleep"] + rng.randint(-30, 30)))
                        if base["sleep"] is not None
                        else None,
                        "pulse": max(1, min(300, base["pulse"] + rng.randint(-5, 5)))
                        if base["pulse"] is not None
                        else None,
                    }
                    c.execute(
                        s.metrics.insert().values(
                            owner=owner,
                            day=day,
                            **encrypt(ring, s.metrics.name, owner, day, values),
                        )
                    )
                save_target(
                    c,
                    ring,
                    owner,
                    anchor.replace(day=1).isoformat(),
                    {
                        "months": 1,
                        "minutes": 750,
                        "fat_drop": 0.8,
                        "activity_weight": 0.6,
                    },
                )
                added += 1
            s.record(c, "operador", "demo.vincular")
    finally:
        engine.dispose()
    return added


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Construir fichas ficticias a partir de perfiles redondeados de ambos estudios."
    )
    parser.add_argument(
        "fitbit_dir",
        type=Path,
        help="Carpeta original de la exportación Fitbit de abril-mayo.",
    )
    parser.add_argument("gym_csv", type=Path)
    args = parser.parse_args()
    print(
        "Perfiles simulados nuevos:",
        load_paired(Settings.load(), args.fitbit_dir, args.gym_csv),
    )
