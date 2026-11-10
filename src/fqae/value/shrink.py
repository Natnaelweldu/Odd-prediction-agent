"""Shrink model probabilities toward the sharp reference (FR-4.2). Weight is fitted on PAST seasons only."""
from __future__ import annotations

import numpy as np


def shrink(p_model, p_ref, w: float):
    """w = weight on the model. w=1 -> raw model, w=0 -> pure market."""
    return w * np.asarray(p_model, float) + (1 - w) * np.asarray(p_ref, float)


def fit_weight(P_model: np.ndarray, P_ref: np.ndarray, y: np.ndarray, grid: int = 41) -> tuple[float, dict]:
    """Pick w in [0,1] minimising log loss of the blend. Returns (w, {w: logloss})."""
    P_model = np.asarray(P_model, float); P_ref = np.asarray(P_ref, float); y = np.asarray(y, int)
    idx = np.arange(len(y))
    curve = {}
    for w in np.linspace(0, 1, grid):
        P = w * P_model + (1 - w) * P_ref
        curve[round(float(w), 4)] = float(-np.mean(np.log(np.clip(P[idx, y], 1e-12, 1))))
    best = min(curve, key=curve.get)
    return best, curve
