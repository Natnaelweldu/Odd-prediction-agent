import numpy as np
import pandas as pd
import pytest

from fqae.models import grid as G
from fqae.risk import caps, flags, kelly
from fqae.value import scan, shrink

NOW = pd.Timestamp("2026-11-14T11:50:00Z")


# ---------- kelly ----------
def test_srs_worked_example():
    assert kelly.full_kelly(0.51, 2.10) == pytest.approx(0.0645, abs=1e-3)
    stake, capped = kelly.stake_fraction(0.51, 2.10)
    assert stake == 0.015 and capped is True


def test_kelly_no_edge_no_stake():
    assert kelly.full_kelly(0.45, 2.0) == 0
    assert kelly.stake_fraction(0.45, 2.0) == (0.0, False)


def test_kelly_uncapped_small_edge():
    stake, capped = kelly.stake_fraction(0.52, 2.0)      # full kelly 0.04 -> quarter 0.01
    assert stake == pytest.approx(0.01) and not capped


# ---------- shrink ----------
def test_shrink_blend_and_srs_example():
    assert shrink.shrink(0.540, 0.480, 0.5) == pytest.approx(0.510)
    assert shrink.shrink(0.6, 0.4, 1.0) == 0.6 and shrink.shrink(0.6, 0.4, 0.0) == 0.4


def test_fit_weight_prefers_market_when_model_is_noise():
    rng = np.random.default_rng(0)
    truth = rng.dirichlet([4, 3, 3], 4000)
    y = np.array([rng.choice(3, p=p) for p in truth])
    ref = truth                                         # market knows the truth
    model = rng.dirichlet([4, 3, 3], 4000)              # model is noise
    w, _ = shrink.fit_weight(model, ref, y)
    assert w <= 0.1
    w2, _ = shrink.fit_weight(truth, truth, y)          # identical inputs: any w equal; no crash
    assert 0 <= w2 <= 1


# ---------- caps ----------
def bet(f, ev, stake, league="E0", date="2026-11-14"):
    return dict(fixture_id=f, league=league, date=date, ev=ev, stake=stake)


def test_correlated_bets_on_same_match_count_once():
    out = caps.apply_caps([bet("a", 0.08, 0.015), bet("a", 0.05, 0.010)])
    assert [b["stake"] for b in out] == [0.015, 0.010]      # second adds no exposure beyond the best bet
    out = caps.apply_caps([bet("a", 0.08, 0.015), bet("a", 0.05, 0.015)], {"per_match": 0.015})
    assert sum(b["stake"] for b in out) == pytest.approx(0.030)   # same size -> still counted once


def test_per_match_cap_limits_larger_second_bet():
    out = caps.apply_caps([bet("a", 0.08, 0.010), bet("a", 0.05, 0.015)], {"per_match": 0.012})
    assert out[1]["stake"] == pytest.approx(0.012) and out[1]["cap_note"]


def test_league_day_and_daily_caps():
    bets = [bet(f"m{i}", 0.09 - i * 0.01, 0.015) for i in range(6)]
    out = caps.apply_caps(bets, {"per_league_day": 0.05, "daily_total": 0.08})
    assert sum(b["stake"] for b in out) == pytest.approx(0.05)
    assert out[-1]["stake"] == 0 and "blocked" in out[-1]["cap_note"]
    mixed = [bet(f"m{i}", 0.09 - i * 0.001, 0.015, league=f"L{i%3}") for i in range(9)]
    out = caps.apply_caps(mixed, {"per_league_day": 0.05, "daily_total": 0.08})
    assert sum(b["stake"] for b in out) == pytest.approx(0.08)


def test_caps_do_not_mutate_input():
    b = [bet("a", 0.05, 0.015)]
    caps.apply_caps(b, {"daily_total": 0.001})
    assert b[0]["stake"] == 0.015


# ---------- flags ----------
def snaps(rows):
    return pd.DataFrame(rows, columns=["bookmaker", "market", "selection", "line", "decimal_odds", "ts_utc"])


def test_price_move_direction():
    s = snaps([("x", "totals", "over", 2.5, 2.00, "2026-11-13T09:00:00Z"),
               ("x", "totals", "over", 2.5, 2.10, "2026-11-14T11:00:00Z")])
    assert flags.price_move(s, "x", "totals", "over", 2.5) == {"open": 2.0, "now": 2.1, "direction": "against_selection"}
    s2 = s.assign(decimal_odds=[2.10, 2.00])
    assert flags.price_move(s2, "x", "totals", "over", 2.5)["direction"] == "toward_selection"
    assert flags.price_move(s.iloc[:1], "x", "totals", "over", 2.5) is None


def test_staleness():
    assert flags.is_fresh("2026-11-14T11:45:00Z", NOW, 10)
    assert not flags.is_fresh("2026-11-14T11:30:00Z", NOW, 10)


# ---------- scan ----------
GRID = G.scoreline_grid(1.7, 1.3, -0.05)


def _snaps(book_over=2.30, book_ts="2026-11-14T11:48:00Z"):
    return snaps([
        ("pinnacle", "totals", "over", 2.5, 1.95, "2026-11-14T11:49:00Z"),
        ("pinnacle", "totals", "under", 2.5, 1.95, "2026-11-14T11:49:00Z"),
        ("bet365", "totals", "over", 2.5, 2.00, "2026-11-13T09:00:00Z"),
        ("bet365", "totals", "over", 2.5, book_over, book_ts),
        ("bet365", "totals", "under", 2.5, 1.70, book_ts),
    ])


def test_candidate_math_is_consistent():
    c = {(x["market"], x["selection"]): x for x in scan.build_candidates(GRID, _snaps(), now=NOW, w=0.5)}
    over = c[("totals", "over")]
    p_raw = G.settle(GRID, "totals", "over", 2.5)["win"]
    assert over["model_prob_raw"] == pytest.approx(p_raw)
    assert over["reference"]["fair_prob"] == pytest.approx(0.5)
    assert over["model_prob_shrunk"] == pytest.approx(0.5 * p_raw + 0.25)
    assert over["ev"] == pytest.approx(over["model_prob_shrunk"] * 2.30 - 1)
    assert over["best_price"]["book"] == "bet365" and over["best_price"]["odds"] == 2.30
    assert over["flags"]["price_move"]["direction"] == "against_selection"
    assert over["stake_pct"] <= 0.015


def test_reference_book_is_never_the_bettable_price():
    out = scan.build_candidates(GRID, _snaps(), now=NOW)
    assert all(c["best_price"]["book"] != "pinnacle" for c in out)


def test_stale_prices_are_rejected():
    out = scan.build_candidates(GRID, _snaps(book_ts="2026-11-14T09:00:00Z"), now=NOW)
    assert out == []


def test_missing_reference_gives_no_candidates():
    s = _snaps(); s = s[s.bookmaker != "pinnacle"]
    assert scan.build_candidates(GRID, s, now=NOW) == []


def test_big_edge_flagged_suspect_not_actionable():
    out = scan.build_candidates(GRID, _snaps(book_over=3.5), now=NOW, ceiling=0.10)
    over = next(c for c in out if c["selection"] == "over")
    assert over["flags"]["suspect_edge"] and not over["actionable"]


def test_1x2_and_asian_handicap_scan():
    s = snaps([
        ("pinnacle", "1x2", "home", None, 2.10, "2026-11-14T11:49:00Z"),
        ("pinnacle", "1x2", "draw", None, 3.50, "2026-11-14T11:49:00Z"),
        ("pinnacle", "1x2", "away", None, 3.60, "2026-11-14T11:49:00Z"),
        ("bet365", "1x2", "home", None, 2.20, "2026-11-14T11:49:00Z"),
        ("pinnacle", "asian_handicap", "home", -0.5, 2.10, "2026-11-14T11:49:00Z"),
        ("pinnacle", "asian_handicap", "away", 0.5, 1.80, "2026-11-14T11:49:00Z"),
        ("bet365", "asian_handicap", "away", 0.5, 1.90, "2026-11-14T11:49:00Z"),
    ])
    out = {(c["market"], c["selection"]): c for c in scan.build_candidates(GRID, s, now=NOW)}
    assert out[("1x2", "home")]["reference"]["fair_prob"] == pytest.approx(
        scan.devig.shin([2.10, 3.50, 3.60])[0])
    ah = out[("asian_handicap", "away")]
    assert ah["line"] == 0.5 and ah["reference"]["fair_prob"] == pytest.approx(scan.devig.shin([2.10, 1.80])[1])
