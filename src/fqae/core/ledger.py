"""Quota ledger (FR-1.3): refuse a call that would exceed the budget, never fail silently."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .config import BUDGETS


class QuotaExceeded(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def window_start(period: str, now: datetime) -> datetime:
    if period == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == "minute":
        return now - timedelta(minutes=1)
    raise ValueError(period)


class Ledger:
    def __init__(self, conn: sqlite3.Connection, budgets: dict | None = None, clock=_now):
        self.conn, self.budgets, self.clock = conn, budgets or BUDGETS, clock

    def used(self, api: str, period: str | None = None) -> int:
        period = period or self.budgets[api]["period"]
        start = _iso(window_start(period, self.clock()))
        r = self.conn.execute("SELECT COALESCE(SUM(cost),0) FROM api_usage WHERE api=? AND ts_utc>=?",
                              (api, start)).fetchone()
        return int(r[0])

    def remaining(self, api: str) -> int:
        return self.budgets[api]["limit"] - self.used(api)

    def check(self, api: str, cost: int = 1) -> None:
        if api not in self.budgets:
            raise KeyError(f"no budget configured for {api!r}")
        b = self.budgets[api]
        used = self.used(api)
        if used + cost > b["limit"]:
            raise QuotaExceeded(f"{api}: {used}+{cost} would exceed {b['limit']}/{b['period']}")

    def record(self, api: str, cost: int = 1, url: str | None = None) -> None:
        self.conn.execute("INSERT INTO api_usage(api, ts_utc, cost, url) VALUES (?,?,?,?)",
                          (api, _iso(self.clock()), cost, url))
        self.conn.commit()
