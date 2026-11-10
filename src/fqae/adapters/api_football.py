"""API-Football fixtures adapter (FR-1.2). Free plan: 100 req/day and limited seasons, so cache everything."""
from __future__ import annotations

import os

from ..core import teams

BASE = "https://v3.football.api-sports.io/fixtures"
SOURCE = "api_football"


def fetch_fixtures(fetcher, league_id: int, season: int, date_from: str, date_to: str, api_key: str | None = None):
    key = api_key or os.environ["API_FOOTBALL_KEY"]
    data, _, cached = fetcher.get_json(
        "api_football", BASE,
        params={"league": league_id, "season": season, "from": date_from, "to": date_to},
        headers={"x-apisports-key": key})
    if data.get("errors"):
        raise RuntimeError(f"API-Football error: {data['errors']}")
    return data["response"], cached


def parse_fixtures(conn, response: list[dict], bootstrap: bool = False) -> list[dict]:
    out = []
    for r in response:
        out.append(dict(
            fixture_id=f"api-football:{r['fixture']['id']}",
            kickoff_utc=r["fixture"]["date"],
            home_id=teams.resolve(conn, SOURCE, r["teams"]["home"]["name"], bootstrap),
            away_id=teams.resolve(conn, SOURCE, r["teams"]["away"]["name"], bootstrap),
            status=r["fixture"]["status"]["short"]))
    return out
