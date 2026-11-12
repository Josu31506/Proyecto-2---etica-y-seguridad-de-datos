"""Only explicit daily activity files. No merging Gym profiles into experimental ground truth."""

import csv
from datetime import datetime
from pathlib import Path


def read_activity(paths):
    rows = {}
    repeated = 0
    for f in sorted(paths):
        with Path(f).open(encoding="utf-8-sig", newline="") as src:
            reader = csv.DictReader(src)
            required = {
                "Id",
                "ActivityDate",
                "VeryActiveMinutes",
                "FairlyActiveMinutes",
                "TotalSteps",
            }
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Faltan columnas de actividad diaria")
            for r in reader:
                subject = r["Id"].strip()
                if not subject.isdigit():
                    raise ValueError("Identificador inválido")
                day = (
                    datetime.strptime(r["ActivityDate"], "%m/%d/%Y").date().isoformat()
                )
                vigorous = int(r["VeryActiveMinutes"])
                moderate = int(r["FairlyActiveMinutes"])
                if min(vigorous, moderate) < 0:
                    raise ValueError("Minutos negativos en la fuente")
                minutes = vigorous + moderate
                steps = int(r["TotalSteps"])
                if not 0 <= minutes <= 1440 or steps < 0:
                    raise ValueError("Medición fuera de dominio")
                key = (subject, day)
                value = {"minutes": minutes, "steps": steps}
                if key in rows:
                    if rows[key] != value:
                        raise ValueError(
                            "Los CSV contienen un día con datos contradictorios"
                        )
                    repeated += 1
                rows[key] = value
    if not rows:
        raise ValueError("No se encontraron registros de actividad")
    return rows, repeated
