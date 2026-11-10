import json
from datetime import datetime, timezone

import pytest

from fqae.core import db
from fqae.core.http import Fetcher
from fqae.core.ledger import Ledger, QuotaExceeded

BUDGETS = {"api_football": {"period": "day", "limit": 2}, "odds_api": {"period": "month", "limit": 5}}


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t


@pytest.fixture
def env(tmp_path):
    conn = db.connect(":memory:")
    clock = Clock(datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc))
    ledger = Ledger(conn, BUDGETS, clock=clock)
    calls = []

    def transport(url, headers):
        calls.append(url)
        return json.dumps({"ok": len(calls)}).encode(), {"x-h": "1"}

    f = Fetcher(ledger, tmp_path, transport, sleep=lambda s: None, today=lambda: "2026-11-10")
    return conn, ledger, f, calls, clock


def test_cache_hit_costs_nothing_and_skips_network(env):
    _, ledger, f, calls, _ = env
    a = f.get_json("api_football", "http://x/f", {"a": 1})
    b = f.get_json("api_football", "http://x/f", {"a": 1})
    assert a[0] == b[0] and a[2] is False and b[2] is True
    assert len(calls) == 1 and ledger.used("api_football") == 1


def test_over_budget_is_refused_not_called(env):
    _, ledger, f, calls, _ = env
    f.get_json("api_football", "http://x/1")
    f.get_json("api_football", "http://x/2")
    with pytest.raises(QuotaExceeded):
        f.get_json("api_football", "http://x/3")
    assert len(calls) == 2


def test_cost_counts_credits(env):
    _, ledger, f, calls, _ = env
    f.get_json("odds_api", "http://x/o", cost=4)
    with pytest.raises(QuotaExceeded):
        f.get_json("odds_api", "http://x/o2", cost=2)
    assert ledger.remaining("odds_api") == 1


def test_secret_never_in_ledger_or_cache_key(env, tmp_path):
    conn, _, f, calls, _ = env
    f.get_json("api_football", "http://x/f", {"a": 1}, secret_params={"apiKey": "SECRET"})
    assert "SECRET" in calls[0]
    assert "SECRET" not in conn.execute("SELECT url FROM api_usage").fetchone()[0]
    assert all("SECRET" not in p.read_text() for p in tmp_path.rglob("*.json"))
    # same request with a different key hits the cache
    assert f.get_json("api_football", "http://x/f", {"a": 1}, secret_params={"apiKey": "OTHER"})[2] is True


def test_daily_window_resets(env):
    _, ledger, f, calls, clock = env
    f.get_json("api_football", "http://x/1"); f.get_json("api_football", "http://x/2")
    clock.t = datetime(2026, 11, 11, 0, 1, tzinfo=timezone.utc)
    f.today = lambda: "2026-11-11"
    f.get_json("api_football", "http://x/3")   # allowed again
    assert len(calls) == 3
