"""The Odds API adapter (FR-1.4). Writes append-only snapshots.

Cost per call = markets x regions credits. Selection convention:
  1x2: home/draw/away.  totals: over/under with line=point.
  asian_handicap (API key 'spreads'): home/away, line = that selection's own handicap.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

BASE = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
MARKET_MAP = {"h2h": "1x2", "totals": "totals", "spreads": "asian_handicap"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_odds(fetcher, sport: str, markets=("h2h", "totals"), regions=("eu",), api_key: str | None = None):
    key = api_key or os.environ["THE_ODDS_API_KEY"]
    cost = len(markets) * len(regions)
    data, hdrs, cached = fetcher.get_json(
        "odds_api", BASE.format(sport=sport),
        params={"regions": ",".join(regions), "markets": ",".join(markets), "oddsFormat": "decimal"},
        secret_params={"apiKey": key}, cost=cost)
    return data, cached


def parse_events(events: list[dict], fetched_utc: str | None = None) -> list[dict]:
    fetched = fetched_utc or _utc_now()
    rows = []
    for ev in events:
        fid = f"odds_api:{ev['id']}"
        home, away = ev["home_team"], ev["away_team"]
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                market = MARKET_MAP.get(mk["key"])
                if not market:
                    continue
                ts = mk.get("last_update") or bk.get("last_update") or fetched
                for o in mk["outcomes"]:
                    name, line = o["name"], o.get("point")
                    if market == "1x2":
                        sel = "draw" if name == "Draw" else "home" if name == home else "away" if name == away else None
                    elif market == "totals":
                        sel = name.lower() if name in ("Over", "Under") else None
                    else:
                        sel = "home" if name == home else "away" if name == away else None
                    if sel is None or not o.get("price") or o["price"] <= 1.0:
                        continue
                    rows.append(dict(fixture_id=fid, bookmaker=bk["key"], market=market, selection=sel,
                                     line=line, decimal_odds=float(o["price"]), ts_utc=ts,
                                     home=home, away=away, commence=ev.get("commence_time")))
    return rows


def store_snapshots(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Insert, skipping exact duplicates (same fixture/book/market/selection/line/ts), so re-runs are safe."""
    n = 0
    for r in rows:
        dup = conn.execute(
            "SELECT 1 FROM odds_snapshots WHERE fixture_id=? AND bookmaker=? AND market=? AND selection=? "
            "AND COALESCE(line,-999)=COALESCE(?,-999) AND ts_utc=? AND decimal_odds=?",
            (r["fixture_id"], r["bookmaker"], r["market"], r["selection"], r["line"], r["ts_utc"],
             r["decimal_odds"])).fetchone()
        if dup:
            continue
        conn.execute(
            "INSERT INTO odds_snapshots(fixture_id,bookmaker,market,selection,line,decimal_odds,ts_utc) "
            "VALUES (?,?,?,?,?,?,?)",
            (r["fixture_id"], r["bookmaker"], r["market"], r["selection"], r["line"], r["decimal_odds"],
             r["ts_utc"]))
        n += 1
    conn.commit()
    return n
