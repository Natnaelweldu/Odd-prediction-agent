"""Check your API keys work. Uses only endpoints that do not spend quota.

Usage: uv run python -m fqae.jobs.smoke_test
"""
import json
import os
import urllib.request

from ..core import config  # noqa: F401  (loads .env)


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()), dict(r.headers)


def check(name, fn):
    try:
        print(f"[ OK ] {name}: {fn()}")
    except KeyError as e:
        print(f"[SKIP] {name}: missing env var {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")


def odds_api():
    d, h = get(f"https://api.the-odds-api.com/v4/sports?apiKey={os.environ['THE_ODDS_API_KEY']}")
    keys = {s["key"] for s in d}
    from ..core.config import ODDS_API_SPORTS
    miss = [k for k in ODDS_API_SPORTS.values() if k not in keys]
    return f"credits remaining={h.get('x-requests-remaining')}, missing sports={miss}"


def api_football():
    d, _ = get("https://v3.football.api-sports.io/status", {"x-apisports-key": os.environ["API_FOOTBALL_KEY"]})
    r = d["response"]
    return f"plan={r['subscription']['plan']}, used today={r['requests']['current']}/{r['requests']['limit_day']}"


def oddspapi():
    d, _ = get(f"https://api.oddspapi.io/v4/sports?apiKey={os.environ['ODDSPAPI_KEY']}")
    return f"{len(d)} sports returned"


if __name__ == "__main__":
    check("The Odds API", odds_api)
    check("API-Football", api_football)
    check("OddsPapi", oddspapi)
