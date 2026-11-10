"""Scoring rules and calibration (FR-6.3)."""
from __future__ import annotations

import numpy as np
from scipy.stats import beta


def log_loss(P: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> float:
    """P: (n, k) probabilities, y: (n,) integer class index."""
    P = np.asarray(P, float); y = np.asarray(y, int)
    return float(-np.mean(np.log(np.clip(P[np.arange(len(y)), y], eps, 1))))


def brier(P: np.ndarray, y: np.ndarray) -> float:
    P = np.asarray(P, float); y = np.asarray(y, int)
    Y = np.eye(P.shape[1])[y]
    return float(np.mean(((P - Y) ** 2).sum(axis=1)))


def rps(P: np.ndarray, y: np.ndarray) -> float:
    """Ranked probability score for ordered outcomes (e.g. H, D, A -> 0, 1, 2)."""
    P = np.asarray(P, float); y = np.asarray(y, int)
    Y = np.eye(P.shape[1])[y]
    cum = np.cumsum(P - Y, axis=1)[:, :-1]
    return float(np.mean((cum ** 2).sum(axis=1) / (P.shape[1] - 1)))


def calibration(p: np.ndarray, hit: np.ndarray, bins: int = 10, alpha: float = 0.05) -> list[dict]:
    """Per-bin predicted mean vs observed frequency with a Clopper-Pearson interval.
    `ok` is True when the mean prediction lies inside the interval (no bin off beyond sampling error)."""
    p = np.asarray(p, float); hit = np.asarray(hit, float)
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    out = []
    for b in range(bins):
        m = which == b
        n = int(m.sum())
        if n == 0:
            continue
        k = int(hit[m].sum())
        lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
        hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
        mp = float(p[m].mean())
        out.append(dict(bin=b, n=n, mean_pred=mp, observed=k / n, lo=float(lo), hi=float(hi), ok=bool(lo <= mp <= hi)))
    return out
