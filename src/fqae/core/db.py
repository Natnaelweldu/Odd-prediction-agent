"""SQLite schema (written to stay Postgres-portable: no SQLite-only types)."""
import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,           -- canonical slug, e.g. 'man_city'
    name    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_aliases (
    source TEXT NOT NULL,               -- 'fd', 'api_football', 'odds_api', ...
    alias  TEXT NOT NULL,
    team_id TEXT NOT NULL REFERENCES teams(team_id),
    PRIMARY KEY (source, alias)
);
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,          -- 'fd:E0:2023-08-11:arsenal:chelsea'
    div TEXT NOT NULL,
    season TEXT NOT NULL,               -- '2324'
    kickoff_utc TEXT,                   -- ISO; date-only rows store 00:00 if time missing
    match_date TEXT NOT NULL,
    home_id TEXT NOT NULL REFERENCES teams(team_id),
    away_id TEXT NOT NULL REFERENCES teams(team_id),
    fthg INTEGER, ftag INTEGER, ftr TEXT,
    hc INTEGER, ac INTEGER, hy INTEGER, ay INTEGER, hr INTEGER, ar INTEGER,
    referee TEXT,
    -- Pinnacle opening / closing 1X2
    psh REAL, psd REAL, psa REAL, psch REAL, pscd REAL, psca REAL,
    -- market average opening / closing 1X2
    avgh REAL, avgd REAL, avga REAL, avgch REAL, avgcd REAL, avgca REAL,
    -- totals 2.5 Pinnacle open/close, avg close
    p_o25 REAL, p_u25 REAL, pc_o25 REAL, pc_u25 REAL, avgc_o25 REAL, avgc_u25 REAL,
    -- Asian handicap (home line) Pinnacle open/close
    ahh REAL, pahh REAL, paha REAL, ahch REAL, pcahh REAL, pcaha REAL
);
CREATE INDEX IF NOT EXISTS idx_matches_div_date ON matches(div, match_date);

CREATE TABLE IF NOT EXISTS odds_snapshots (   -- append-only
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,                      -- may be NULL until fixture is resolved
    fixture_id TEXT NOT NULL,           -- 'odds_api:<id>' / 'api-football:<id>'
    bookmaker TEXT NOT NULL,
    market TEXT NOT NULL,               -- '1x2', 'totals', 'asian_handicap'
    selection TEXT NOT NULL,            -- 'home','draw','away','over','under'
    line REAL,                          -- totals / AH line, NULL for 1x2
    decimal_odds REAL NOT NULL CHECK (decimal_odds > 1.0),
    ts_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snap_fixture ON odds_snapshots(fixture_id, market, ts_utc);

CREATE TRIGGER IF NOT EXISTS odds_snapshots_no_update
BEFORE UPDATE ON odds_snapshots BEGIN
    SELECT RAISE(ABORT, 'odds_snapshots is append-only');
END;
CREATE TRIGGER IF NOT EXISTS odds_snapshots_no_delete
BEFORE DELETE ON odds_snapshots BEGIN
    SELECT RAISE(ABORT, 'odds_snapshots is append-only');
END;

CREATE TABLE IF NOT EXISTS api_usage (
    api TEXT NOT NULL,
    ts_utc TEXT NOT NULL,
    cost INTEGER NOT NULL DEFAULT 1,
    url TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_api_ts ON api_usage(api, ts_utc);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version TEXT PRIMARY KEY,
    trained_from TEXT, trained_to TEXT,
    params_json TEXT, metrics_json TEXT,
    data_snapshot_id TEXT, seed INTEGER, created_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id TEXT NOT NULL, model_version TEXT NOT NULL REFERENCES model_versions(model_version),
    market TEXT NOT NULL, selection TEXT NOT NULL, line REAL,
    prob_raw REAL NOT NULL, prob_shrunk REAL, created_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS paper_bets (
    bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id TEXT NOT NULL, market TEXT NOT NULL, selection TEXT NOT NULL, line REAL,
    bookmaker TEXT, odds REAL NOT NULL, ts_utc TEXT NOT NULL,
    model_version TEXT, stake_pct REAL NOT NULL,
    closing_odds REAL, clv REAL, result TEXT
);
"""


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DB_PATH
    if str(p) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
