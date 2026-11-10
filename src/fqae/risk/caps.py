"""Exposure caps (FR-5.2). Bets on the same match are correlated: only the largest counts toward caps."""
from __future__ import annotations

from collections import defaultdict

DEFAULT_CAPS = {"per_match": 0.02, "per_league_day": 0.05, "daily_total": 0.08}   # proposed, tune later


def apply_caps(bets: list[dict], caps: dict | None = None) -> list[dict]:
    """bets: dicts with fixture_id, league, date, ev, stake (fraction). Processed best-EV first.
    Returns the same dicts with 'stake' possibly reduced and 'cap_note' set. Input is not mutated."""
    caps = {**DEFAULT_CAPS, **(caps or {})}
    out = [dict(b, cap_note=None) for b in sorted(bets, key=lambda b: -b["ev"])]
    match_max = defaultdict(float)            # correlated bets: exposure = max stake on that match
    league_day = defaultdict(float); day = defaultdict(float)
    for b in out:
        s, cur = b["stake"], match_max[b["fixture_id"]]
        extra = max(0.0, s - cur)                    # new exposure this bet adds on top of the match's best bet
        allowed = max(0.0, min(extra, caps["per_match"] - cur,
                               caps["per_league_day"] - league_day[(b["league"], b["date"])],
                               caps["daily_total"] - day[b["date"]]))
        final = s if extra == 0 else min(s, cur + allowed)
        if final < s - 1e-12:
            b["cap_note"] = "reduced by exposure caps" if final > 0 else "blocked by exposure caps"
        b["stake"] = final
        match_max[b["fixture_id"]] += allowed
        league_day[(b["league"], b["date"])] += allowed
        day[b["date"]] += allowed
    return out
