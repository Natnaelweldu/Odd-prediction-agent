from fqae.adapters import odds_api
from fqae.core import db

EVENTS = [{
    "id": "abc123", "home_team": "Arsenal", "away_team": "Chelsea", "commence_time": "2026-11-14T15:00:00Z",
    "bookmakers": [{
        "key": "pinnacle", "last_update": "2026-11-10T09:00:00Z",
        "markets": [
            {"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 1.9}, {"name": "Chelsea", "price": 4.2},
                                        {"name": "Draw", "price": 3.6}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 2.1, "point": 2.5},
                                           {"name": "Under", "price": 1.8, "point": 2.5}]},
            {"key": "spreads", "outcomes": [{"name": "Arsenal", "price": 1.95, "point": -0.5},
                                            {"name": "Chelsea", "price": 1.95, "point": 0.5}]},
            {"key": "btts", "outcomes": [{"name": "Yes", "price": 1.7}]},
        ]}]}]


def test_parse_maps_markets_and_selections():
    rows = odds_api.parse_events(EVENTS)
    assert len(rows) == 7   # 3 + 2 + 2, btts ignored
    by = {(r["market"], r["selection"]): r for r in rows}
    assert by[("1x2", "draw")]["decimal_odds"] == 3.6
    assert by[("totals", "over")]["line"] == 2.5
    assert by[("asian_handicap", "home")]["line"] == -0.5
    assert by[("asian_handicap", "away")]["line"] == 0.5
    assert rows[0]["fixture_id"] == "odds_api:abc123" and rows[0]["ts_utc"] == "2026-11-10T09:00:00Z"


def test_store_is_idempotent_and_append_only():
    conn = db.connect(":memory:")
    rows = odds_api.parse_events(EVENTS)
    assert odds_api.store_snapshots(conn, rows) == 7
    assert odds_api.store_snapshots(conn, rows) == 0
    # a price change at a later time is a NEW row (history preserved)
    EV2 = [dict(EVENTS[0], bookmakers=[dict(EVENTS[0]["bookmakers"][0], last_update="2026-11-10T10:00:00Z",
            markets=[{"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 1.85}]}])])]
    assert odds_api.store_snapshots(conn, odds_api.parse_events(EV2)) == 1
    assert conn.execute("SELECT COUNT(*) FROM odds_snapshots WHERE selection='home' AND market='1x2'").fetchone()[0] == 2
