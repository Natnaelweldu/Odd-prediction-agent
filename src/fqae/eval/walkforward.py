"""Walk-forward backtest (FR-6.3): train on the past, predict the next block, never look ahead."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from ..models import grid as G
from ..models.dixon_coles import DixonColes
from ..value import devig


def load_matches(conn: sqlite3.Connection, divs=None) -> pd.DataFrame:
    q = """SELECT match_id, div, season, match_date AS date, home_id AS home, away_id AS away,
                  fthg AS hg, ftag AS ag, ftr, psch, pscd, psca, pc_o25, pc_u25, avgch, avgcd, avgca
           FROM matches WHERE fthg IS NOT NULL ORDER BY match_date, match_id"""
    df = pd.read_sql_query(q, conn)
    df["date"] = pd.to_datetime(df["date"])
    return df if divs is None else df[df["div"].isin(divs)].reset_index(drop=True)


def _run_league(args) -> pd.DataFrame:
    df, test_seasons, xi, block_days, window_days = args
    out = []
    test = df[df["season"].isin(test_seasons)]
    t0, t1 = test["date"].min(), test["date"].max()
    start = t0
    while start <= t1:
        end = start + pd.Timedelta(days=block_days)
        block = test[(test["date"] >= start) & (test["date"] < end)]
        if len(block):
            train = df[(df["date"] < start) & (df["date"] >= start - pd.Timedelta(days=window_days))]
            m = DixonColes(xi=xi).fit(train, as_of=start)
            for r in block.itertuples():
                if r.home not in m.attack or r.away not in m.attack:
                    out.append(dict(match_id=r.match_id, skipped=True)); continue
                g = m.grid(r.home, r.away)
                p = G.probs_1x2(g)
                out.append(dict(match_id=r.match_id, skipped=False, ph=p["home"], pd_=p["draw"], pa=p["away"],
                                p_over25=G.settle(g, "totals", "over", 2.5)["win"],
                                lam=m.lambdas(r.home, r.away)[0], mu=m.lambdas(r.home, r.away)[1],
                                model_version=f"dc-xi{xi}-{start.date()}"))
        start = end
    return pd.DataFrame(out)


def walk_forward(df: pd.DataFrame, test_seasons: list[str], xi: float = 0.0019, block_days: int = 14,
                 window_days: int = 1500, workers: int = 4) -> pd.DataFrame:
    """Returns one row per test match with model probabilities and the (de-vigged) market reference."""
    jobs = [(g.reset_index(drop=True), test_seasons, xi, block_days, window_days) for _, g in df.groupby("div")]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        preds = pd.concat(list(ex.map(_run_league, jobs)), ignore_index=True)
    res = df.merge(preds, on="match_id", how="inner")
    res = res[~res["skipped"].astype(bool)].copy()
    # market reference: Pinnacle close, Shin de-vigged
    def mk(r, cols, k):
        o = [r[c] for c in cols]
        return devig.shin(o) if not any(pd.isna(x) or x <= 1.0 for x in o) else np.full(k, np.nan)
    m3 = np.vstack([mk(r, ["psch", "pscd", "psca"], 3) for _, r in res.iterrows()])
    res[["mh", "md", "ma"]] = m3
    m2 = np.vstack([mk(r, ["pc_o25", "pc_u25"], 2) for _, r in res.iterrows()])
    res["m_over25"] = m2[:, 0]
    res["y"] = res["ftr"].map({"H": 0, "D": 1, "A": 2})
    res["over25"] = ((res["hg"] + res["ag"]) > 2.5).astype(int)
    return res
