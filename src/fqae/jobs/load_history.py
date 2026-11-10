"""Load every data/raw/<season>_<div>.csv into the DB and print rows per league/season.

Usage: python -m fqae.jobs.load_history [--bootstrap]
  --bootstrap  auto-register unseen football-data team names (first load only; review afterwards)
"""
import sys

from ..adapters import fd_csv
from ..core import db


def main(argv=None):
    bootstrap = "--bootstrap" in (argv or sys.argv[1:])
    conn = db.connect()
    counts = fd_csv.ingest_dir(conn, bootstrap=bootstrap)
    if not counts:
        print(f"No CSVs found in {fd_csv.RAW_DIR}. Expected names like 2324_E0.csv")
        return 1
    for k, v in counts.items():
        print(f"{k}: {v} matches")
    print("teams:", conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0])
    from ..core import quality
    issues = quality.run_checks(conn)
    print(f"data-quality issues: {len(issues)}")
    for i in issues[:50]:
        print("  -", i)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
