"""One cheap live call (1 Odds API credit): which bookmakers are returned, is Pinnacle among them?

Usage: uv run python -m fqae.jobs.live_check [sport_key] [regions]
Example: uv run python -m fqae.jobs.live_check soccer_epl eu
Also stores the returned prices as odds snapshots, so the call is not wasted.
"""
import os
import sys
from collections import Counter

from ..adapters import odds_api
from ..core import config, db
from ..core.http import Fetcher
from ..core.ledger import Ledger


def summarise(events: list[dict]) -> dict:
    books = Counter(b["key"] for e in events for b in e.get("bookmakers", []))
    return {"events": len(events), "bookmakers": dict(books.most_common()), "pinnacle": "pinnacle" in books,
            "first_kickoff": min((e["commence_time"] for e in events), default=None)}


def main(argv=None):
    argv = argv or sys.argv[1:]
    sport = argv[0] if argv else "soccer_epl"
    regions = tuple(argv[1].split(",")) if len(argv) > 1 else ("eu",)
    conn = db.connect()
    fetcher = Fetcher(Ledger(conn))
    key = os.environ["THE_ODDS_API_KEY"]
    data, hdrs, cached = fetcher.get_json(
        "odds_api", odds_api.BASE.format(sport=sport),
        params={"regions": ",".join(regions), "markets": "h2h", "oddsFormat": "decimal"},
        secret_params={"apiKey": key}, cost=len(regions))
    s = summarise(data)
    print(f"{'(from cache) ' if cached else ''}{sport} regions={regions}: {s['events']} upcoming events, "
          f"credits remaining={hdrs.get('x-requests-remaining', '?')}")
    print("bookmakers:", ", ".join(f"{k}({v})" for k, v in s["bookmakers"].items()) or "none")
    print("PINNACLE PRESENT:", s["pinnacle"])
    n = odds_api.store_snapshots(conn, odds_api.parse_events(data))
    print(f"stored {n} new odds snapshots")


if __name__ == "__main__":
    main()
