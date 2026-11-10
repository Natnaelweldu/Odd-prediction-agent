"""Risk flags computed from stored snapshots, never from narration (FR-5.3)."""
from __future__ import annotations

import pandas as pd


def price_move(snaps: pd.DataFrame, bookmaker: str, market: str, selection: str, line) -> dict | None:
    """Open vs latest price for one book/selection. Lengthening odds = market moved AGAINST the selection."""
    s = snaps[(snaps.bookmaker == bookmaker) & (snaps.market == market) & (snaps.selection == selection)]
    s = s[(s.line.isna()) if line is None or pd.isna(line) else (s.line == line)].sort_values("ts_utc")
    if len(s) < 2:
        return None
    o, n = float(s.decimal_odds.iloc[0]), float(s.decimal_odds.iloc[-1])
    d = "flat" if abs(n - o) < 1e-9 else "against_selection" if n > o else "toward_selection"
    return {"open": o, "now": n, "direction": d}


def margin(odds: list[float]) -> float:
    return sum(1 / o for o in odds) - 1


def is_fresh(ts_utc: str, now: pd.Timestamp, max_age_min: float = 10.0) -> bool:
    return (now - pd.Timestamp(ts_utc)).total_seconds() <= max_age_min * 60
