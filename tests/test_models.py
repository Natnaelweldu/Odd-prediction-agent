import numpy as np
import pandas as pd
import pytest

from fqae.eval import metrics
from fqae.models import grid as G
from fqae.models.dixon_coles import DixonColes
from fqae.value import devig


# ---------- grid / settlement ----------
def test_grid_sums_to_one_and_1x2_sums_to_one():
    g = G.scoreline_grid(1.6, 1.1, rho=-0.1)
    assert g.sum() == pytest.approx(1)
    assert sum(G.probs_1x2(g).values()) == pytest.approx(1)


def test_independent_poisson_matches_closed_form():
    g = G.scoreline_grid(1.0, 1.0, rho=0.0, max_goals=20)
    assert G.probs_1x2(g)["home"] == pytest.approx(G.probs_1x2(g)["away"])
    from scipy.stats import poisson
    assert G.settle(g, "totals", "over", 2.5)["win"] == pytest.approx(1 - poisson.cdf(2, 2.0), abs=1e-6)


def test_win_push_lose_sum_to_one_for_all_lines():
    g = G.scoreline_grid(1.7, 1.0, rho=-0.08)
    for line in [-2, -1.75, -1.5, -1.25, -1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1, 1.5]:
        for sel in ("home", "away"):
            o = G.settle(g, "asian_handicap", sel, line)
            assert o["win"] + o["push"] + o["lose"] == pytest.approx(1)
    for line in [1.5, 2, 2.25, 2.5, 2.75, 3]:
        for sel in ("over", "under"):
            o = G.settle(g, "totals", sel, line)
            assert o["win"] + o["push"] + o["lose"] == pytest.approx(1)


def test_ah_known_settlements_on_degenerate_grids():
    def point(i, j):
        g = np.zeros((11, 11)); g[i, j] = 1; return g
    s = G.settle
    # home wins 1-0
    assert s(point(1, 0), "asian_handicap", "home", -1) == {"win": 0.0, "push": 1.0, "lose": 0.0}
    assert s(point(1, 0), "asian_handicap", "home", -0.5)["win"] == 1
    assert s(point(1, 0), "asian_handicap", "home", -1.5)["lose"] == 1
    # quarter line -0.75 on a 1-goal win = half loss (lose half stake): modelled as win 0, push .5? -> lose .5 push .5? check:
    # -0.75 splits to -0.5 (win) and -1.0 (push): half win, half push
    o = s(point(1, 0), "asian_handicap", "home", -0.75)
    assert (o["win"], o["push"], o["lose"]) == (0.5, 0.5, 0.0)
    # -0.25 on a draw splits to 0 (push) and -0.5 (lose): half loss
    o = s(point(1, 1), "asian_handicap", "home", -0.25)
    assert (o["win"], o["push"], o["lose"]) == (0.0, 0.5, 0.5)
    # +0.25 away on a draw: 0 (push) + 0.5 (win) = half win
    o = s(point(1, 1), "asian_handicap", "away", 0.25)
    assert (o["win"], o["push"], o["lose"]) == (0.5, 0.5, 0.0)
    # totals: 3 goals vs over 3 = push; over 2.75 = half win(2.5 win, 3 push)
    assert s(point(2, 1), "totals", "over", 3)["push"] == 1
    o = s(point(2, 1), "totals", "over", 2.75)
    assert (o["win"], o["push"], o["lose"]) == (0.5, 0.5, 0.0)
    o = s(point(1, 1), "totals", "under", 2.25)   # 2 goals: under 2 push, under 2.5 win
    assert (o["win"], o["push"], o["lose"]) == (0.5, 0.5, 0.0)


def test_ah_home_and_away_are_complements():
    g = G.scoreline_grid(1.4, 1.2, rho=-0.05)
    h = G.settle(g, "asian_handicap", "home", -0.75); a = G.settle(g, "asian_handicap", "away", 0.75)
    assert h["win"] == pytest.approx(a["lose"]) and h["lose"] == pytest.approx(a["win"])


def test_ev_formula():
    o = {"win": 0.51, "push": 0.0, "lose": 0.49}
    assert G.ev(o, 2.10) == pytest.approx(0.071)   # SRS worked example


# ---------- devig ----------
@pytest.mark.parametrize("m", ["multiplicative", "power", "shin"])
def test_devig_sums_to_one_and_symmetric(m):
    assert devig.devig([1.9, 3.6, 4.2], m).sum() == pytest.approx(1)
    assert devig.devig([1.9, 1.9], m) == pytest.approx([0.5, 0.5])


def test_multiplicative_known_value():
    p = devig.multiplicative([1.8, 2.1])
    q = np.array([1 / 1.8, 1 / 2.1]); assert p == pytest.approx(q / q.sum())


def test_shin_and_power_shrink_longshot_vs_multiplicative():
    odds = [1.25, 5.5, 12.0]
    assert devig.shin(odds)[2] < devig.multiplicative(odds)[2]
    assert devig.power(odds)[2] < devig.multiplicative(odds)[2]


def test_fair_odds_unchanged():
    assert devig.shin([2.0, 2.0]) == pytest.approx([0.5, 0.5])
    assert devig.overround([2.0, 2.0]) == pytest.approx(0)


# ---------- metrics ----------
def test_metrics_known_values():
    P = np.array([[1, 0, 0], [0.2, 0.3, 0.5]]); y = np.array([0, 2])
    assert metrics.brier(P, y) == pytest.approx((0 + (0.04 + 0.09 + 0.25)) / 2)
    assert metrics.log_loss(P, y) == pytest.approx(-np.log(0.5) / 2)
    assert metrics.rps(np.array([[1, 0, 0]]), np.array([2])) == pytest.approx(1.0)
    assert metrics.rps(np.array([[1, 0, 0]]), np.array([0])) == 0


def test_calibration_flags_miscalibration():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, 20000)
    good = metrics.calibration(p, rng.random(20000) < p)
    bad = metrics.calibration(p, rng.random(20000) < np.clip(p + 0.15, 0, 1))
    assert sum(not b["ok"] for b in good) <= 1     # 95% intervals: allow a fluke
    assert sum(not b["ok"] for b in bad) >= 5


# ---------- Dixon-Coles ----------
def _simulate(n_teams=12, seasons=6, seed=1):
    rng = np.random.default_rng(seed)
    att = rng.normal(0, 0.25, n_teams); att -= att.mean()
    dfn = rng.normal(0, 0.2, n_teams); dfn -= dfn.mean()
    ha = 0.3
    rows, day = [], 0
    for _ in range(seasons):
        for i in range(n_teams):
            for j in range(n_teams):
                if i == j: continue
                lam = np.exp(0.15 + att[i] + dfn[j] + ha); mu = np.exp(0.15 + att[j] + dfn[i])
                rows.append((pd.Timestamp("2018-08-01") + pd.Timedelta(days=day // 6), f"T{i}", f"T{j}",
                             rng.poisson(lam), rng.poisson(mu)))
                day += 1
    return pd.DataFrame(rows, columns=["date", "home", "away", "hg", "ag"]), att, dfn, ha


def test_dc_recovers_parameters_on_synthetic_data():
    df, att, dfn, ha = _simulate()
    m = DixonColes(xi=0.0).fit(df)
    est = np.array([m.attack[f"T{i}"] for i in range(len(att))])
    assert m.converged
    assert np.corrcoef(est, att)[0, 1] > 0.9
    assert m.home_adv == pytest.approx(ha, abs=0.1)
    assert abs(m.rho) < 0.15


def test_dc_has_no_lookahead():
    df, *_ = _simulate(seasons=2)
    cut = df["date"].iloc[len(df) // 2]
    a = DixonColes(xi=0.001).fit(df, as_of=cut)
    b = DixonColes(xi=0.001).fit(df[df["date"] < cut], as_of=cut)
    assert a.n_matches == b.n_matches == (df["date"] < cut).sum()
    assert a.home_adv == pytest.approx(b.home_adv)


def test_dc_grid_is_consistent_with_lambdas():
    df, *_ = _simulate(seasons=2)
    m = DixonColes().fit(df)
    g = m.grid("T0", "T1")
    assert g.sum() == pytest.approx(1)
    lam, mu = m.lambdas("T0", "T1")
    assert (g.sum(axis=1) @ np.arange(g.shape[0])) == pytest.approx(lam, rel=0.05)
