"""Trusted offline lab on the public archives. Never imported by the HTTP service."""

import csv, json
from collections import defaultdict
from pathlib import Path
from statistics import fmean
import numpy as np
from diffprivlib.mechanisms import Laplace
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from .privacy import private_mean, contributions, LIMIT
from .dataio import read_activity

GRID = (0.1, 0.5, 1.0, 2.0)


def analyze_fitbit(path, period="2016-04", trials=300):
    rows, duplicates = read_activity([path])
    records = [
        (u, d, m["minutes"]) for (u, d), m in rows.items() if d.startswith(period)
    ]
    values = contributions(records)
    if not values:
        raise ValueError("No hay datos de ese periodo.")
    grouped = defaultdict(list)
    for u, d, m in records:
        grouped[u].append(m)
    observed = [fmean(v) for v in grouped.values()]
    counts = [len(v) for v in grouped.values()]
    summary = {
        "processed_days": len(rows),
        "people_in_file": len(set(u for u, _ in rows)),
        "period": period,
        "people_in_period": len(values),
        "observed_days_in_period": len(records),
        "coverage_min_days": min(counts),
        "coverage_max_days": max(counts),
        "identical_duplicates": duplicates,
        "clipped_people": sum(x > LIMIT for x in observed),
        "unclipped_reference": round(fmean(observed), 3),
        "reference": round(fmean(values), 3),
        "row_weighted_reference": round(fmean(r[2] for r in records), 3),
    }
    result = []
    for eps in GRID:
        rng = np.random.RandomState(3031)
        samples = [private_mean(values, eps, rng=rng) for _ in range(trials)]
        errors = np.array([abs(x - fmean(values)) for x in samples if x is not None])
        result.append(
            {
                "epsilon": eps,
                "draws": trials,
                "returned_pct": round(100 * len(errors) / trials, 1),
                "mae_minutes": round(float(errors.mean()), 3) if len(errors) else None,
                "p90_abs_error": round(float(np.percentile(errors, 90)), 3)
                if len(errors)
                else None,
            }
        )
    return summary, result


def gym_records(path):
    # No ID linking Gym examples to Fitbit. The guarantee for this lab is row-level.
    result = []
    seen = set()
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key = tuple(r.values())
            if key in seen:
                continue
            seen.add(key)
            exp = int(r["Experience_Level"])
            freq = int(r["Workout_Frequency (days/week)"])
            if exp not in range(1, 4) or freq not in range(1, 8):
                raise ValueError("Categoría de Gym fuera del dominio predefinido")
            duration = float(r["Session_Duration (hours)"])
            if not np.isfinite(duration) or not 0 <= duration <= 24:
                raise ValueError("Duración inválida")
            result.append(
                ((exp - 1) * 7 + freq - 1, int(duration >= 1.25), r["Gender"])
            )
    return result


def model_lab(path, repeats=30):
    """Classifier is post-processing of ONE histogram with global L1 sensitivity 1.
    Only the 42 sanitized cells would be DP, not the raw validation metrics.
    """
    data = gym_records(path)
    idx = np.arange(len(data))
    tr, te = train_test_split(idx, test_size=0.3, random_state=3031, shuffle=True)
    X = np.array([r[0] for r in data])
    y = np.array([r[1] for r in data])
    group = np.array([r[2] for r in data])
    train_counts = np.zeros((21, 2))
    np.add.at(train_counts, (X[tr], y[tr]), 1)

    def score(counts):
        pos = (counts[:, 1] + 1) / (counts.sum(axis=1) + 2)
        score = pos[X]
        pred = (score >= 0.5).astype(int)
        confidence = np.where(y == 1, score, 1 - score)
        values = np.r_[confidence[tr], confidence[te]]
        labels = np.r_[np.ones(len(tr)), np.zeros(len(te))]
        fpr, tpr, _ = roc_curve(labels, values)
        groups = {
            str(g): {
                "n": int((group[te] == g).sum()),
                "accuracy": float(
                    accuracy_score(y[te][group[te] == g], pred[te][group[te] == g])
                ),
            }
            for g in sorted(set(group[te]))
        }
        return {
            "accuracy": float(accuracy_score(y[te], pred[te])),
            "balanced_accuracy": float(balanced_accuracy_score(y[te], pred[te])),
            "attack_auc": float(roc_auc_score(labels, values)),
            "attack_advantage": float(max(tpr - fpr)),
        }, groups

    base, base_groups = score(train_counts)
    output = []
    group_metrics = {}
    for eps in GRID:
        rng = np.random.RandomState(11)
        scores = []
        gs = defaultdict(list)
        for run in range(repeats):
            mechanism = Laplace(epsilon=eps, sensitivity=1, random_state=rng)
            noisy = np.array(
                [max(0.0, mechanism.randomise(c)) for c in train_counts.flat]
            ).reshape(train_counts.shape)
            scores1, groups = score(noisy)
            scores.append(scores1)
            for g, v in groups.items():
                gs[g].append(v["accuracy"])
        output.append(
            {
                "epsilon": eps,
                **{k: round(fmean(d[k] for d in scores), 4) for k in base},
                "accuracy_sd": round(float(np.std([d["accuracy"] for d in scores])), 4),
            }
        )
        group_metrics[str(eps)] = {g: round(fmean(v), 4) for g, v in gs.items()}
    return {
        "task": "Duración de sesión >= 75 minutos; evaluación por fila del archivo Gym",
        "train": len(tr),
        "test": len(te),
        "baseline": base,
        "baseline_groups": base_groups,
        "private": output,
        "private_group_accuracy": group_metrics,
        "repetitions": repeats,
    }


def run(root):
    resultdir = root / "evidence"
    resultdir.mkdir(exist_ok=True)
    summary, utility = analyze_fitbit(root / "data/raw/dailyActivity_merged.csv")
    model = model_lab(root / "data/raw/gym_members_exercise_tracking.csv")
    evidence = {
        "scope": "Laboratorio offline con archivos públicos. Referencias exactas y semillas experimentales; no es una publicación DP.",
        "fitbit": summary,
        "utility": utility,
        "gym": model,
    }
    (resultdir / "experimentos.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    return evidence


if __name__ == "__main__":
    from .config import ROOT

    result = run(ROOT)
    print(
        json.dumps(
            {
                "fitbit": result["fitbit"],
                "utility": result["utility"],
                "model": result["gym"]["private"],
            },
            indent=2,
        )
    )
