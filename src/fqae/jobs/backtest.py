"""Usage: uv run python -m fqae.jobs.backtest --seasons 2223 2324 --xi 0.001 0.0019 0.003"""
import argparse

from ..core import db
from ..eval import report, walkforward as W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", required=True)
    ap.add_argument("--xi", nargs="+", type=float, default=[0.0019])
    ap.add_argument("--divs", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--save")
    a = ap.parse_args()
    df = W.load_matches(db.connect(), a.divs)
    for xi in a.xi:
        res = W.walk_forward(df, a.seasons, xi=xi, workers=a.workers)
        print(f"\n===== xi={xi} seasons={a.seasons} =====")
        print(report.fmt(report.summarise(res)))
        if a.save:
            res.to_csv(f"{a.save}_xi{xi}.csv", index=False)


if __name__ == "__main__":
    main()
