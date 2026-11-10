"""Turn a model grid + stored odds snapshots into value candidates (Module 4 + 5, SRS section 6 schema)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import grid as G
from ..risk import flags, kelly
from . import devig, shrink

TWO_WAY = {"totals": ("over", "under"), "asian_handicap": ("home", "away")}


def latest_per_book(snaps: pd.DataFrame) -> pd.DataFrame:
    s = snaps.sort_values("ts_utc")
    return s.groupby(["bookmaker", "market", "selection", "line"], dropna=False).tail(1)


def _reference(latest: pd.DataFrame, market: str, line, ref_book: str, method: str):
    """De-vigged reference probabilities {selection: p} from the reference book, or None if incomplete."""
    r = latest[(latest.bookmaker == ref_book) & (latest.market == market)]
    if market == "1x2":
        o = {x.selection: x.decimal_odds for x in r.itertuples()}
        if set(o) != {"home", "draw", "away"}: return None
        keys = ["home", "draw", "away"]
        return dict(zip(keys, devig.devig([o[k] for k in keys], method))), margin_of(o.values())
    a, b = TWO_WAY[market]
    la, lb = (line, line) if market == "totals" else (line, -line)
    oa = r[(r.selection == a) & np.isclose(r.line.astype(float), la)]
    ob = r[(r.selection == b) & np.isclose(r.line.astype(float), lb)]
    if oa.empty or ob.empty: return None
    p = devig.devig([float(oa.decimal_odds.iloc[0]), float(ob.decimal_odds.iloc[0])], method)
    return {a: p[0], b: p[1]}, margin_of([oa.decimal_odds.iloc[0], ob.decimal_odds.iloc[0]])


def margin_of(odds) -> float:
    return flags.margin(list(map(float, odds)))


def build_candidates(grid: np.ndarray, snaps: pd.DataFrame, *, now: pd.Timestamp, w: float = 0.5,
                     ref_book: str = "pinnacle", devig_method: str = "shin", min_ev: float = 0.03,
                     ceiling: float = 0.10, max_age_min: float = 10.0, kelly_mult: float = 0.25,
                     stake_cap: float = 0.015, exclude_books=("pinnacle",)) -> list[dict]:
    """One candidate per (market, selection, line) where the best fresh non-reference price shows EV.
    Everything numeric comes from this function; nothing here touches an LLM."""
    latest = latest_per_book(snaps)
    fresh = latest[latest.ts_utc.map(lambda t: flags.is_fresh(t, now, max_age_min))]
    out = []
    seen = set()
    for r in fresh.itertuples():
        # AH away lines map to the home-line key so both sides share one reference
        key = (r.market, r.selection, None if pd.isna(r.line) else float(r.line))
        if key in seen: continue
        seen.add(key)
        market, sel, line = key
        book_rows = fresh[(fresh.market == market) & (fresh.selection == sel) & ~fresh.bookmaker.isin(exclude_books)]
        book_rows = book_rows[book_rows.line.isna()] if line is None else book_rows[np.isclose(book_rows.line.astype(float), line)]
        if book_rows.empty: continue
        best = book_rows.loc[book_rows.decimal_odds.idxmax()]
        ref_line = line if (market != "asian_handicap" or sel == "home") else -line
        ref = _reference(latest, market, ref_line, ref_book, devig_method)
        if ref is None: continue
        refp, ref_margin = ref
        o = G.settle(grid, market, sel, line)
        p_raw = G.p_equiv(o)
        p_ref = refp[sel]
        p_s = float(shrink.shrink(p_raw, p_ref, w))
        push = o["push"]
        eff = {"win": p_s * (1 - push), "push": push, "lose": (1 - p_s) * (1 - push)}
        odds = float(best.decimal_odds)
        ev = G.ev(eff, odds)
        stake, capped = kelly.stake_fraction(p_s, odds, kelly_mult, stake_cap) if ev > 0 else (0.0, False)
        mv = flags.price_move(snaps, best.bookmaker, market, sel, line)
        out.append({
            "market": market, "selection": sel, "line": line,
            "best_price": {"book": best.bookmaker, "odds": odds, "timestamp_utc": best.ts_utc},
            "reference": {"book": ref_book, "devig_method": devig_method, "fair_prob": float(p_ref)},
            "model_prob_raw": float(p_raw), "shrink_weight": w, "model_prob_shrunk": p_s,
            "edge_vs_reference": p_s - float(p_ref), "ev": ev,
            "kelly_fraction": kelly_mult, "stake_pct": stake, "stake_capped": capped,
            "flags": {"price_move": mv, "books_quoting": int(book_rows.bookmaker.nunique()),
                      "reference_margin": ref_margin, "suspect_edge": ev > ceiling, "llm_facts_used": False},
            "actionable": min_ev <= ev <= ceiling,
            "clv": None,
        })
    return sorted(out, key=lambda c: -c["ev"])
