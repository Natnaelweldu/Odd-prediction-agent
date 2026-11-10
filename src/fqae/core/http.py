"""One door for every outbound call: cache -> ledger check -> rate limit -> transport (FR-1.2/1.3)."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR, MIN_INTERVAL_S
from .ledger import Ledger


def urllib_transport(url: str, headers: dict) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), {k.lower(): v for k, v in r.headers.items()}


class Fetcher:
    def __init__(self, ledger: Ledger, cache_dir: Path | None = None, transport=urllib_transport,
                 sleep=time.sleep, monotonic=time.monotonic, today=None):
        self.ledger = ledger
        self.cache_dir = Path(cache_dir or DATA_DIR / "cache")
        self.transport, self.sleep, self.monotonic = transport, sleep, monotonic
        self.today = today or (lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        self._last: dict[str, float] = {}

    @staticmethod
    def _key(url: str, params: dict, day: str) -> str:
        qs = urllib.parse.urlencode(sorted(params.items()))
        return hashlib.sha256(f"{day}|{url}?{qs}".encode()).hexdigest()

    def get_json(self, api: str, url: str, params: dict | None = None, secret_params: dict | None = None,
                 headers: dict | None = None, cost: int = 1, refresh: bool = False):
        """Returns (data, response_headers, from_cache). Secrets are never part of the cache key or ledger."""
        params = params or {}
        path = self.cache_dir / api / f"{self._key(url, params, self.today())}.json"
        if path.exists() and not refresh:   # same URL is never fetched twice in a day
            blob = json.loads(path.read_text())
            return blob["data"], blob["headers"], True
        self.ledger.check(api, cost)        # raises QuotaExceeded, does not call
        wait = MIN_INTERVAL_S.get(api, 0) - (self.monotonic() - self._last.get(api, -1e9))
        if wait > 0:
            self.sleep(wait)
        full = {**params, **(secret_params or {})}
        full_url = f"{url}?{urllib.parse.urlencode(full)}" if full else url
        self._last[api] = self.monotonic()
        self.ledger.record(api, cost, url=f"{url}?{urllib.parse.urlencode(sorted(params.items()))}")
        body, hdrs = self.transport(full_url, headers or {})
        data = json.loads(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"data": data, "headers": hdrs}))
        return data, hdrs, False
