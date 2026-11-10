"""Git-friendly store for the scheduled job: immutable gzip CSV per pull + usage log + small state file.
No merge conflicts (every pull writes a NEW file) and the data branch history is the audit trail."""
from __future__ import annotations

import gzip
import io
import json
import sqlite3
from pathlib import Path

import pandas as pd

SNAP_COLS = ["fixture_id", "bookmaker", "market", "selection", "line", "decimal_odds", "ts_utc",
             "home", "away", "commence", "pull_ts", "league", "reason"]


class Store:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        (self.root / "snapshots").mkdir(parents=True, exist_ok=True)

    # ---- snapshots ----
    def write_snapshots(self, rows: list[dict], pull_ts: str, league: str, reason: str) -> Path | None:
        if not rows:
            return None
        df = pd.DataFrame(rows).assign(pull_ts=pull_ts, league=league, reason=reason)[SNAP_COLS]
        name = pull_ts.replace(":", "").replace("-", "")
        p = self.root / "snapshots" / pull_ts[:10] / f"{name}_{league}_{reason}.csv.gz"
        p.parent.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO(); df.to_csv(buf, index=False)
        p.write_bytes(gzip.compress(buf.getvalue().encode(), mtime=0))
        return p

    def read_snapshots(self) -> pd.DataFrame:
        files = sorted((self.root / "snapshots").rglob("*.csv.gz"))
        if not files:
            return pd.DataFrame(columns=SNAP_COLS)
        return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

    # ---- usage ledger ----
    @property
    def usage_path(self) -> Path:
        return self.root / "usage.csv"

    def hydrate_usage(self, conn: sqlite3.Connection) -> int:
        if not self.usage_path.exists():
            return 0
        df = pd.read_csv(self.usage_path)
        conn.executemany("INSERT INTO api_usage(api, ts_utc, cost, url) VALUES (?,?,?,?)",
                         [(r.api, r.ts_utc, int(r.cost), r.url if isinstance(r.url, str) else None)
                          for r in df.itertuples()])
        conn.commit()
        return len(df)

    def append_usage(self, conn: sqlite3.Connection, skip: int) -> int:
        """Append api_usage rows added after the first `skip` rows (the hydrated ones)."""
        rows = conn.execute("SELECT api, ts_utc, cost, url FROM api_usage ORDER BY rowid LIMIT -1 OFFSET ?",
                            (skip,)).fetchall()
        rows = [r for r in rows if r["cost"] > 0]
        if rows:
            new = not self.usage_path.exists()
            pd.DataFrame([tuple(r) for r in rows], columns=["api", "ts_utc", "cost", "url"]).to_csv(
                self.usage_path, mode="a", header=new, index=False)
        return len(rows)

    # ---- state ----
    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def load_state(self) -> dict:
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else {"last_pull": {}}

    def save_state(self, st: dict) -> None:
        self.state_path.write_text(json.dumps(st, indent=1, sort_keys=True))
