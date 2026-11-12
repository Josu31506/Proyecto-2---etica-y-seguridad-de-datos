"""Pure epsilon-DP at person level, add/remove adjacency. No fixed RNG in serving."""

from collections import defaultdict
from statistics import fmean
from math import isfinite
from diffprivlib.mechanisms import Laplace

LIMIT = 120.0  # public, predeclared minutes per person-day
MIN_NOISY_N = 8.0  # threshold only on the *private* count
EPSILON = 1.0
PERIODS = ("2016-04", "2016-05")


def contributions(records):
    """Input: unique (subject, date, minutes). Mean per observed person, not per row."""
    days = defaultdict(dict)
    for subject, day, minutes in records:
        if not isfinite(minutes) or not 0 <= minutes <= 1440:
            raise ValueError("Minutos fuera de dominio")
        if day in days[subject] and days[subject][day] != minutes:
            raise ValueError("Día duplicado con valores incompatibles")
        days[subject][day] = minutes
    return [
        min(LIMIT, max(0.0, fmean(measures.values()))) for measures in days.values()
    ]


def private_mean(values, epsilon=EPSILON, *, rng=None):
    """Two sequential mechanisms; sensitivity 60 and 1, epsilon/2 each.
    rng only for reproducible LOCAL evaluation. API never supplies it.
    Even an empty dataset takes the same noisy path.
    """
    if not isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon debe ser positivo")
    if any(not isfinite(x) or not 0 <= x <= LIMIT for x in values):
        raise ValueError("Aporte no acotado")
    center = LIMIT / 2
    total = Laplace(
        epsilon=epsilon / 2, sensitivity=center, random_state=rng
    ).randomise(sum(x - center for x in values))
    count = Laplace(epsilon=epsilon / 2, sensitivity=1, random_state=rng).randomise(
        len(values)
    )
    if count < MIN_NOISY_N:
        return None
    return round(min(LIMIT, max(0.0, center + total / count)), 1)
