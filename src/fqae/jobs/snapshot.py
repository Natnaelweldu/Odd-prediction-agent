"""Scheduled odds-snapshot job (runs from GitHub Actions; safe to run any time, usually does nothing).

Per run:  1) list upcoming events per league (free endpoint, 0 credits)
          2) decide per league whether to spend credits now ('open' Thu/Fri, 'close' just before kickoff)
          3) pull odds, write an immutable snapshot file to the store, record credits used.
Usage: uv run python -m fqae.jobs.snapshot --store store [--dry-run] [--force-open]
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from ..adapters import odds_api
from ..core import config as C
from ..core import db
from ..core.http import Fetcher
from ..core.ledger import Ledger, QuotaExceeded
from ..core.store import Store

EVENTS_URL = "https://api.the-odds-api.com/v4/sports/{sport}/events"


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def decide(events: list[dict], league_state: dict, now: datetime, credits_left: float,
           cost: int, force_open: bool = False) -> str | None:
    """Return 'close', 'open' or None for one league. Pure function (tested)."""
    if credits_left < cost or not events:
        return None
    kicks = sorted(datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) for e in events)
    ago = lambda k: (now - datetime.fromisoformat(league_state[k].replace("Z", "+00:00"))
                     if k in league_state else timedelta(days=999))
    last_any = min(ago("close"), ago("open"))
    if any(timedelta(0) < k - now <= timedelta(minutes=C.CLOSE_WINDOW_MIN) for k in kicks) \
            and last_any >= timedelta(minutes=C.CLOSE_MIN_GAP_MIN):
        return "close"
    open_ok = (force_open or now.weekday() in C.OPEN_WEEKDAYS) and credits_left >= C.OPEN_CREDIT_RESERVE
    if open_ok and any(timedelta(0) < k - now <= timedelta(hours=C.OPEN_HORIZON_H) for k in kicks) \
            and ago("open") >= timedelta(hours=C.OPEN_MIN_GAP_H):
        return "open"
    return None


def run(store_dir: str, now: datetime | None = None, dry_run: bool = False, force_open: bool = False,
        fetcher: Fetcher | None = None, conn=None, api_key: str | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    store = Store(store_dir)
    conn = conn or db.connect(":memory:")
    hydrated = store.hydrate_usage(conn)
    ledger = Ledger(conn, clock=lambda: now)
    import tempfile
    fetcher = fetcher or Fetcher(ledger, cache_dir=tempfile.mkdtemp(prefix="fqae-cache-"))
    key = api_key or os.environ.get("THE_ODDS_API_KEY", "")
    state = store.load_state()
    cost = len(C.LIVE_MARKETS) * len(C.LIVE_REGIONS)
    done = []
    for div in C.LIVE_LEAGUES:
        sport = C.ODDS_API_SPORTS[div]
        events, _, _ = fetcher.get_json("odds_api", EVENTS_URL.format(sport=sport),
                                        secret_params={"apiKey": key}, cost=0, refresh=True)
        ls = state["last_pull"].setdefault(sport, {})
        reason = decide(events, ls, now, ledger.remaining("odds_api"), cost, force_open)
        print(f"{sport}: {len(events)} events -> {reason or 'skip'}  (credits left {ledger.remaining('odds_api')})")
        if reason is None or dry_run:
            continue
        try:
            data, hdrs, _ = fetcher.get_json(
                "odds_api", odds_api.BASE.format(sport=sport),
                params={"regions": ",".join(C.LIVE_REGIONS), "markets": ",".join(C.LIVE_MARKETS),
                        "oddsFormat": "decimal"},
                secret_params={"apiKey": key}, cost=cost, refresh=True)
        except QuotaExceeded as e:
            print("quota guard:", e); break
        rows = odds_api.parse_events(data, iso(now))
        p = store.write_snapshots(rows, iso(now), sport, reason)
        ls[reason] = iso(now)
        state["credits_remaining_reported"] = hdrs.get("x-requests-remaining")
        print(f"  {reason}: {len(rows)} prices -> {p}; API says {hdrs.get('x-requests-remaining')} credits left")
        done.append({"sport": sport, "reason": reason, "rows": len(rows)})
    store.save_state(state)
    store.append_usage(conn, hydrated)
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="store")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-open", action="store_true")
    a = ap.parse_args()
    run(a.store, dry_run=a.dry_run, force_open=a.force_open)


if __name__ == "__main__":
    main()
