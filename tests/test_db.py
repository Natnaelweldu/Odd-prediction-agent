import sqlite3

import pytest

from fqae.core import db


def test_odds_snapshots_are_append_only():
    c = db.connect(":memory:")
    c.execute("INSERT INTO odds_snapshots(fixture_id,bookmaker,market,selection,decimal_odds,ts_utc) "
              "VALUES ('x','pinnacle','1x2','home',2.0,'2026-11-10T10:00:00Z')")
    with pytest.raises(sqlite3.DatabaseError):
        c.execute("UPDATE odds_snapshots SET decimal_odds=3.0")
    with pytest.raises(sqlite3.DatabaseError):
        c.execute("DELETE FROM odds_snapshots")


def test_odds_must_be_above_one():
    c = db.connect(":memory:")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO odds_snapshots(fixture_id,bookmaker,market,selection,decimal_odds,ts_utc) "
                  "VALUES ('x','b','1x2','home',0.9,'t')")
