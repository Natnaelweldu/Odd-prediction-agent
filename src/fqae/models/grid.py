"""Exact scoreline grid and market derivation (FR-3.2). No Monte Carlo."""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson

MAX_GOALS = 10


def dc_tau(i, j, lam, mu, rho):
    if i == 0 and j == 0: return 1 - lam * mu * rho
    if i == 0 and j == 1: return 1 + lam * rho
    if i == 1 and j == 0: return 1 + mu * rho
    if i == 1 and j == 1: return 1 - rho
    return 1.0


def scoreline_grid(lam: float, mu: float, rho: float = 0.0, max_goals: int = MAX_GOALS) -> np.ndarray:
    """G[i, j] = P(home scores i, away scores j), Dixon-Coles corrected, renormalised."""
    g = np.outer(poisson.pmf(np.arange(max_goals + 1), lam), poisson.pmf(np.arange(max_goals + 1), mu))
    for i in (0, 1):
        for j in (0, 1):
            g[i, j] *= dc_tau(i, j, lam, mu, rho)
    return g / g.sum()


def probs_1x2(g: np.ndarray) -> dict:
    return {"home": float(np.tril(g, -1).sum()), "draw": float(np.trace(g)), "away": float(np.triu(g, 1).sum())}


def _settle_half(g: np.ndarray, stat: str, sign: int, line: float) -> tuple[float, float, float]:
    """(win, push, lose) probabilities for a single (non-quarter) line.
    stat='diff': home - away goals.  stat='total': home + away goals.
    The bet wins when sign*stat + line > 0 (for totals Over use sign=+1, line=-L; Under sign=-1, line=+L)."""
    n = g.shape[0]
    i, j = np.indices((n, n))
    s = (i - j) if stat == "diff" else (i + j)
    margin = sign * s + line
    # exact float compare is safe: half-lines never tie, integer lines are exact in float
    return float(g[margin > 1e-9].sum()), float(g[np.abs(margin) <= 1e-9].sum()), float(g[margin < -1e-9].sum())


def settle(g: np.ndarray, market: str, selection: str, line: float | None = None) -> dict:
    """Return {'win','push','lose'} (half-win/half-loss folded in) for a market selection.
    Quarter lines are split into two half-stake bets on the adjacent lines.
    asian_handicap: `line` is the selection's own handicap (home -0.75 means home gives 0.75).
    totals: `line` is the goal line L."""
    if market == "1x2":
        p = probs_1x2(g)
        return {"win": p[selection], "push": 0.0, "lose": 1 - p[selection]}
    if market == "asian_handicap":
        stat, sign = "diff", (1 if selection == "home" else -1)
        eff = lambda l: l
    elif market == "totals":
        stat, sign = "total", (1 if selection == "over" else -1)
        eff = lambda l: -l if selection == "over" else l
    else:
        raise ValueError(market)
    # split quarter lines
    frac = round((abs(line) * 4)) % 4   # 1 or 3 => quarter line
    parts = [line - 0.25, line + 0.25] if frac in (1, 3) else [line]
    res = np.array([_settle_half(g, stat, sign, eff(l)) for l in parts]).mean(axis=0)
    return {"win": float(res[0]), "push": float(res[1]), "lose": float(res[2])}


def ev(o: dict, decimal_odds: float) -> float:
    """Expected profit per unit stake given settle() probabilities (pushes return stake)."""
    return o["win"] * (decimal_odds - 1) - o["lose"]


def p_equiv(o: dict) -> float:
    """Push-excluded win probability: comparable with a de-vigged two-way price."""
    d = o["win"] + o["lose"]
    return o["win"] / d if d > 0 else 0.5
