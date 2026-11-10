"""Time-weighted Dixon-Coles fit (FR-3.1). Own implementation (scipy), no extra dependency."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .grid import scoreline_grid


class DixonColes:
    def __init__(self, xi: float = 0.0019, max_goals: int = 10):
        """xi: per-day decay (0.0019 ~ half-life 365 days). Main tuned parameter."""
        self.xi, self.max_goals = xi, max_goals
        self.teams: list[str] = []

    def fit(self, df: pd.DataFrame, as_of=None) -> "DixonColes":
        """df columns: date, home, away, hg, ag. Only rows with date < as_of are used."""
        d = df.copy()
        d["date"] = pd.to_datetime(d["date"])
        as_of = pd.Timestamp(as_of) if as_of is not None else d["date"].max() + pd.Timedelta(days=1)
        d = d[d["date"] < as_of]
        self.teams = sorted(set(d["home"]) | set(d["away"]))
        idx = {t: k for k, t in enumerate(self.teams)}
        n = len(self.teams)
        h = d["home"].map(idx).to_numpy(); a = d["away"].map(idx).to_numpy()
        x = d["hg"].to_numpy(float); y = d["ag"].to_numpy(float)
        w = np.exp(-self.xi * (as_of - d["date"]).dt.days.to_numpy(float))
        self.as_of, self.n_matches = as_of, len(d)

        def unpack(p):
            att = np.append(p[: n - 1], -p[: n - 1].sum())      # sum-to-zero
            dfn = np.append(p[n - 1: 2 * n - 2], -p[n - 1: 2 * n - 2].sum())
            return att, dfn, p[-3], p[-2], p[-1]

        def nll(p):
            att, dfn, c, ha, rho = unpack(p)
            lam = np.exp(c + att[h] + dfn[a] + ha); mu = np.exp(c + att[a] + dfn[h])
            tau = np.ones_like(lam)
            m00 = (x == 0) & (y == 0); m01 = (x == 0) & (y == 1)
            m10 = (x == 1) & (y == 0); m11 = (x == 1) & (y == 1)
            tau[m00] = 1 - lam[m00] * mu[m00] * rho
            tau[m01] = 1 + lam[m01] * rho
            tau[m10] = 1 + mu[m10] * rho
            tau[m11] = 1 - rho
            if np.any(tau <= 0):
                return 1e10
            ll = np.log(tau) + x * np.log(lam) - lam + y * np.log(mu) - mu   # constants dropped
            return -(w * ll).sum()

        p0 = np.zeros(2 * n - 2 + 3); p0[-3] = 0.1; p0[-2] = 0.25
        res = minimize(nll, p0, method="L-BFGS-B",
                       bounds=[(None, None)] * (2 * n - 2) + [(-1.0, 1.5), (-0.5, 1.0), (-0.3, 0.3)])
        att, dfn, self.intercept, self.home_adv, self.rho = unpack(res.x)
        self.attack = dict(zip(self.teams, att)); self.defence = dict(zip(self.teams, dfn))
        self.converged = bool(res.success)
        return self

    def lambdas(self, home: str, away: str) -> tuple[float, float]:
        """Expected goals (λ home, λ away). Raises KeyError for teams not seen in training."""
        lam = np.exp(self.intercept + self.attack[home] + self.defence[away] + self.home_adv)
        mu = np.exp(self.intercept + self.attack[away] + self.defence[home])
        return float(lam), float(mu)

    def grid(self, home: str, away: str, lam_scale: tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
        lam, mu = self.lambdas(home, away)
        return scoreline_grid(lam * lam_scale[0], mu * lam_scale[1], self.rho, self.max_goals)

    def params(self) -> dict:
        return {"xi": self.xi, "intercept": self.intercept, "home_adv": self.home_adv, "rho": self.rho, "n_matches": self.n_matches,
                "as_of": str(self.as_of.date()), "attack": self.attack, "defence": self.defence}
