"""Remove bookmaker margin (FR-4.1): multiplicative, power, Shin."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def _q(odds) -> np.ndarray:
    o = np.asarray(odds, float)
    if np.any(o <= 1.0):
        raise ValueError("decimal odds must be > 1")
    return 1.0 / o


def overround(odds) -> float:
    return float(_q(odds).sum() - 1.0)


def multiplicative(odds) -> np.ndarray:
    q = _q(odds)
    return q / q.sum()


def power(odds) -> np.ndarray:
    """p_i = q_i ** k with k >= 1 chosen so the probabilities sum to 1."""
    q = _q(odds)
    if abs(q.sum() - 1) < 1e-12:
        return q
    k = brentq(lambda k: (q ** k).sum() - 1.0, 1.0, 50.0)
    return q ** k


def shin(odds) -> np.ndarray:
    """Shin (1992/93) insider-trading model."""
    q = _q(odds); b = q.sum()
    if abs(b - 1) < 1e-12:
        return q
    def probs(z):
        return (np.sqrt(z * z + 4 * (1 - z) * q * q / b) - z) / (2 * (1 - z))
    z = brentq(lambda z: probs(z).sum() - 1.0, 1e-9, 0.999)
    p = probs(z)
    return p / p.sum()


METHODS = {"multiplicative": multiplicative, "power": power, "shin": shin}


def devig(odds, method: str = "shin") -> np.ndarray:
    return METHODS[method](odds)
