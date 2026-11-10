import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from fqae.core import db
from fqae.core.http import Fetcher
from fqae.core.ledger import Ledger
from fqae.core.store import Store
from fqae.jobs import snapshot

UTC = timezone.utc
SAT_NOON = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)      # Saturday
THU_9 = datetime(2026, 11, 12, 9, 0, tzinfo=UTC)          # Thursday


def ev(kick):
    return {"id": "e1", "home_team": "Arsenal", "away_team": "Chelsea", "commence_time": kick}


def test_decide_close_window_and_gap():
    e = [ev("2026-11-14T12:20:00Z")]
    assert snapshot.decide(e, {}, SAT_NOON, 400, 2) == "close"
    assert snapshot.decide(e, {"close": "2026-11-14T11:55:00Z"}, SAT_NOON, 400, 2) is None   # pulled 5 min ago
    assert snapshot.decide(e, {"close": "2026-11-14T11:40:00Z"}, SAT_NOON, 400, 2) == "close"
    assert snapshot.decide([ev("2026-11-14T14:00:00Z")], {}, SAT_NOON, 400, 2) is None      # too early
    assert snapshot.decide([ev("2026-11-14T11:50:00Z")], {}, SAT_NOON, 400, 2) is None      # already started


def test_decide_open_only_thu_fri_with_reserve():
    e = [ev("2026-11-14T15:00:00Z")]
    assert snapshot.decide(e, {}, THU_9, 400, 2) == "open"
    assert snapshot.decide(e, {"open": "2026-11-12T08:00:00Z"}, THU_9, 400, 2) is None       # too soon after last open
    assert snapshot.decide(e, {}, THU_9, 100, 2) is None                                      # below reserve
    wed = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
    assert snapshot.decide(e, {}, wed, 400, 2) is None                                        # not an open day
    assert snapshot.decide([ev("2026-11-14T06:00:00Z")], {}, wed, 400, 2, force_open=True) == "open"
    assert snapshot.decide(e, {}, THU_9, 1, 2) is None                                        # cannot afford
    assert snapshot.decide([], {}, THU_9, 400, 2) is None


ODDS = [{"id": "e1", "home_team": "Arsenal", "away_team": "Chelsea", "commence_time": "2026-11-14T12:20:00Z",
         "bookmakers": [{"key": "pinnacle", "last_update": "2026-11-14T11:59:00Z", "markets": [
             {"key": "h2h", "outcomes": [{"name": "Arsenal", "price": 1.9}, {"name": "Chelsea", "price": 4.2},
                                         {"name": "Draw", "price": 3.6}]}]}]}]


def make(tmp_path, now):
    calls = []

    def transport(url, headers):
        calls.append(url)
        if "/events" in url:
            body = [ev("2026-11-14T12:20:00Z")] if "soccer_epl" in url else []
        else:
            body = ODDS
        return json.dumps(body).encode(), {"x-requests-remaining": "480"}

    conn = db.connect(":memory:")
    ledger = Ledger(conn, clock=lambda: now)
    f = Fetcher(ledger, tmp_path / "cache", transport, sleep=lambda s: None, today=lambda: "2026-11-14")
    return conn, f, calls


def test_end_to_end_pull_persist_and_no_double_pull(tmp_path):
    store = tmp_path / "store"
    conn, f, calls = make(tmp_path, SAT_NOON)
    done = snapshot.run(str(store), now=SAT_NOON, fetcher=f, conn=conn, api_key="K")
    assert done == [{"sport": "soccer_epl", "reason": "close", "rows": 3}]
    files = list((store / "snapshots").rglob("*.csv.gz"))
    assert len(files) == 1 and "soccer_epl_close" in files[0].name
    snaps = Store(store).read_snapshots()
    assert len(snaps) == 3 and set(snaps.bookmaker) == {"pinnacle"} and snaps.reason.iloc[0] == "close"
    usage = pd.read_csv(store / "usage.csv")
    assert usage.cost.sum() == 2 and (usage.api == "odds_api").all()      # free events calls not logged
    assert "K" not in (store / "usage.csv").read_text()                    # key never persisted

    # a second run 5 minutes later (fresh process: new conn, hydrated from the store) must not pull again
    later = datetime(2026, 11, 14, 12, 5, tzinfo=UTC)
    conn2, f2, calls2 = make(tmp_path / "b", later)
    assert snapshot.run(str(store), now=later, fetcher=f2, conn=conn2, api_key="K") == []
    assert not any("/odds" in c for c in calls2)
    assert pd.read_csv(store / "usage.csv").cost.sum() == 2


def test_dry_run_spends_nothing(tmp_path):
    conn, f, calls = make(tmp_path, SAT_NOON)
    assert snapshot.run(str(tmp_path / "s"), now=SAT_NOON, dry_run=True, fetcher=f, conn=conn, api_key="K") == []
    assert not any("/odds" in c for c in calls)


def test_monthly_budget_is_respected_across_runs(tmp_path):
    store = tmp_path / "store"
    Store(store)
    pd.DataFrame([("odds_api", "2026-11-02T10:00:00Z", 449, "x")], columns=["api", "ts_utc", "cost", "url"]) \
        .to_csv(store / "usage.csv", index=False)
    conn, f, calls = make(tmp_path, SAT_NOON)
    assert snapshot.run(str(store), now=SAT_NOON, fetcher=f, conn=conn, api_key="K") == []   # 1 credit left < cost 2
    assert not any("/odds" in c for c in calls)


def test_store_import_roundtrip(tmp_path):
    from fqae.adapters.odds_api import store_snapshots
    store = tmp_path / "store"
    conn, f, _ = make(tmp_path, SAT_NOON)
    snapshot.run(str(store), now=SAT_NOON, fetcher=f, conn=conn, api_key="K")
    df = Store(store).read_snapshots()
    c2 = db.connect(":memory:")
    assert store_snapshots(c2, df.where(df.notna(), None).to_dict("records")) == 3
    assert store_snapshots(c2, df.where(df.notna(), None).to_dict("records")) == 0
