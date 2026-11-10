import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_env(path: Path | None = None) -> None:
    """Minimal .env loader (no dependency). Real environment variables win.
    Looks in the working directory (and its parents) first, then next to the source tree."""
    candidates = [path] if path else [*(p / ".env" for p in [Path.cwd(), *Path.cwd().parents]), ROOT / ".env"]
    for f in candidates:
        if f.is_file():
            for line in f.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


load_env()
DATA_DIR = Path(os.environ.get("FQAE_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = Path(os.environ.get("FQAE_DB", DATA_DIR / "fqae.sqlite"))

# football-data.co.uk division codes -> league name
LEAGUES = {
    "E0": "Premier League",
    "E1": "Championship",
    "SP1": "La Liga",
    "I1": "Serie A",
    "D1": "Bundesliga",
    "F1": "Ligue 1",
}

# Odds API sport keys for our leagues
ODDS_API_SPORTS = {
    "E0": "soccer_epl", "E1": "soccer_efl_champ", "SP1": "soccer_spain_la_liga",
    "I1": "soccer_italy_serie_a", "D1": "soccer_germany_bundesliga", "F1": "soccer_france_ligue_one",
}

# Hard budgets, set slightly under the free-tier limits so we never hit the wall.
# period: 'day' | 'month' | 'minute'.  Confirm limits on each vendor page (they change).
BUDGETS = {
    "api_football": {"period": "day", "limit": 90},       # free plan: 100/day
    "odds_api": {"period": "month", "limit": 450},        # free plan: 500 credits/month
    "oddspapi": {"period": "month", "limit": 225},        # free tier: 250/month
    "football_data_org": {"period": "minute", "limit": 9},  # 10/min
}
MIN_INTERVAL_S = {"api_football": 1.0, "odds_api": 1.0, "oddspapi": 1.0, "football_data_org": 6.0}

# Live snapshot job (GitHub Actions). Championship skipped to save Odds API credits.
LIVE_LEAGUES = ["E0", "SP1", "I1", "D1", "F1"]
LIVE_MARKETS = ("h2h", "totals")        # add "spreads" (Asian handicap) when credits allow: +1 credit/pull
LIVE_REGIONS = ("eu",)
OPEN_WEEKDAYS = {3, 4}                  # Thu, Fri (Monday=0): pull "opening" prices for the weekend
OPEN_HORIZON_H = 72                     # only if a match kicks off within this many hours
OPEN_MIN_GAP_H = 20
CLOSE_WINDOW_MIN = 25                   # pull when a kickoff is within this many minutes
CLOSE_MIN_GAP_MIN = 12                  # don't pull the same league twice within this gap
OPEN_CREDIT_RESERVE = 150               # below this many credits left, only closing pulls run
