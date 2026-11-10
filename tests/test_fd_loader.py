from pathlib import Path

import pytest

from fqae.adapters import fd_csv
from fqae.core import db, teams

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def conn():
    return db.connect(":memory:")


def test_unmapped_teams_block_ingest(conn):
    with pytest.raises(teams.UnknownTeam):
        fd_csv.ingest(conn, fd_csv.read_csv(FIX / "2324_E0.csv"), "E0", "2324")


def test_ingest_one_row_per_match(conn):
    n = fd_csv.ingest(conn, fd_csv.read_csv(FIX / "2324_E0.csv"), "E0", "2324", bootstrap=True)
    assert n == 3
    rows = conn.execute("SELECT * FROM matches ORDER BY match_date, match_id").fetchall()
    assert len(rows) == 3
    r = rows[0]
    assert r["match_id"] == "fd:E0:2023-08-11:burnley:man_city"
    assert (r["fthg"], r["ftag"], r["ftr"]) == (0, 3, "A")
    assert r["psch"] == 12.0 and r["hc"] == 2 and r["referee"] == "C Pawson"
    assert r["pcahh"] == 1.95


def test_reingest_is_idempotent(conn):
    df = fd_csv.read_csv(FIX / "2324_E0.csv")
    fd_csv.ingest(conn, df, "E0", "2324", bootstrap=True)
    fd_csv.ingest(conn, df, "E0", "2324")
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 3


def test_missing_columns_become_null(conn):
    df = fd_csv.read_csv(FIX / "2324_E0.csv").drop(columns=["PSCH", "AvgCH"])
    fd_csv.ingest(conn, df, "E0", "2324", bootstrap=True)
    r = conn.execute("SELECT psch, avgch FROM matches LIMIT 1").fetchone()
    assert r["psch"] is None and r["avgch"] is None
