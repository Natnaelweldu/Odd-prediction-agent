"""football-data.co.uk CSV adapter (FR-1.1). One row per match."""
from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pandas as pd

from ..core import teams
from ..core.config import RAW_DIR

BASE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
SOURCE = "fd"

# csv column -> db column
COLMAP = {
    "FTHG": "fthg", "FTAG": "ftag", "FTR": "ftr",
    "HC": "hc", "AC": "ac", "HY": "hy", "AY": "ay", "HR": "hr", "AR": "ar",
    "Referee": "referee",
    "PSH": "psh", "PSD": "psd", "PSA": "psa",
    "PSCH": "psch", "PSCD": "pscd", "PSCA": "psca",
    "AvgH": "avgh", "AvgD": "avgd", "AvgA": "avga",
    "AvgCH": "avgch", "AvgCD": "avgcd", "AvgCA": "avgca",
    "P>2.5": "p_o25", "P<2.5": "p_u25",
    "PC>2.5": "pc_o25", "PC<2.5": "pc_u25",
    "AvgC>2.5": "avgc_o25", "AvgC<2.5": "avgc_u25",
    "AHh": "ahh", "PAHH": "pahh", "PAHA": "paha",
    "AHCh": "ahch", "PCAHH": "pcahh", "PCAHA": "pcaha",
}
INT_COLS = {"fthg", "ftag", "hc", "ac", "hy", "ay", "hr", "ar"}
DB_COLS = ["match_id", "div", "season", "kickoff_utc", "match_date", "home_id", "away_id",
           *COLMAP.values()]


def csv_path(season: str, div: str) -> Path:
    return RAW_DIR / f"{season}_{div}.csv"


def read_csv(src) -> pd.DataFrame:
    """Read a football-data CSV (path or bytes). Tolerates junk trailing rows/columns."""
    if isinstance(src, (bytes, bytearray)):
        src = io.BytesIO(src)
    df = pd.read_csv(src, encoding="latin-1", on_bad_lines="skip")
    df = df.dropna(subset=["HomeTeam", "AwayTeam", "Date"]).copy()
    df["Date"] = df["Date"].astype(str).str.strip()
    return df


def _parse_date(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    alt = pd.to_datetime(s, format="%d/%m/%y", errors="coerce")
    return d.fillna(alt)


def normalise(df: pd.DataFrame, div: str, season: str, conn: sqlite3.Connection,
              bootstrap: bool = False) -> pd.DataFrame:
    """Return rows ready for the matches table. Raises UnknownTeam unless bootstrap=True."""
    dates = _parse_date(df["Date"])
    if dates.isna().any():
        raise ValueError(f"{div} {season}: unparseable dates in rows {list(df.index[dates.isna()])[:5]}")
    out = pd.DataFrame(index=df.index)
    out["div"], out["season"] = div, season
    out["match_date"] = dates.dt.strftime("%Y-%m-%d")
    times = df["Time"].fillna("00:00").astype(str) if "Time" in df else "00:00"
    # football-data times are UK local; stored as-is, labelled by kickoff_utc only approx.
    out["kickoff_utc"] = out["match_date"] + "T" + times + ":00"
    out["home_id"] = [teams.resolve(conn, SOURCE, n.strip(), bootstrap) for n in df["HomeTeam"]]
    out["away_id"] = [teams.resolve(conn, SOURCE, n.strip(), bootstrap) for n in df["AwayTeam"]]
    for src, dst in COLMAP.items():
        out[dst] = df[src] if src in df else None
    for c in INT_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
    out["match_id"] = ("fd:" + div + ":" + out["match_date"] + ":" + out["home_id"] + ":" + out["away_id"])
    return out[DB_COLS]


def ingest(conn: sqlite3.Connection, df: pd.DataFrame, div: str, season: str,
           bootstrap: bool = False) -> int:
    rows = normalise(df, div, season, conn, bootstrap)
    rows = rows.astype(object).where(rows.notna(), None)
    sql = (f"INSERT OR REPLACE INTO matches({','.join(DB_COLS)}) "
           f"VALUES ({','.join('?' * len(DB_COLS))})")
    conn.executemany(sql, [tuple(None if v is pd.NA else v for v in r) for r in rows.itertuples(index=False)])
    conn.commit()
    return len(rows)


def ingest_dir(conn: sqlite3.Connection, folder: Path = RAW_DIR, bootstrap: bool = False) -> dict:
    """Load every '<season>_<div>.csv' in folder (e.g. 2324_E0.csv)."""
    counts = {}
    for p in sorted(Path(folder).glob("*_*.csv")):
        season, div = p.stem.split("_", 1)
        counts[p.stem] = ingest(conn, read_csv(p), div, season, bootstrap)
    return counts


def download(season: str, div: str, fetch) -> Path:
    """Fetch one CSV via `fetch(url)->bytes` (cache + quota ledger arrive in tasks 0.5/0.6)."""
    p = csv_path(season, div)
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(fetch(BASE_URL.format(season=season, div=div)))
    return p
