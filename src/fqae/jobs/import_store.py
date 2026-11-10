"""Load every snapshot file from the data store into the local SQLite odds_snapshots table.
Usage: uv run python -m fqae.jobs.import_store store"""
import sys

from ..adapters.odds_api import store_snapshots
from ..core import db
from ..core.store import Store


def main():
    conn = db.connect()
    df = Store(sys.argv[1] if len(sys.argv) > 1 else "store").read_snapshots()
    rows = df.where(df.notna(), None).to_dict("records")
    print(f"{len(rows)} rows in store -> {store_snapshots(conn, rows)} new rows inserted")


if __name__ == "__main__":
    main()
