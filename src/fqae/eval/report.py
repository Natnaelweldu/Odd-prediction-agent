"""Backtest summary: model vs de-vigged Pinnacle close vs naive baseline (Gate A inputs)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics


def summarise(res: pd.DataFrame) -> dict:
    r = res.dropna(subset=["mh", "md", "ma"])
    y = r["y"].to_numpy(int)
    M = r[["ph", "pd_", "pa"]].to_numpy(); K = r[["mh", "md", "ma"]].to_numpy()
    base = np.tile(np.bincount(y, minlength=3) / len(y), (len(y), 1))
    out = {"n_1x2": len(r)}
    for name, P in (("model", M), ("market", K), ("naive", base)):
        out[name] = dict(log_loss=metrics.log_loss(P, y), brier=metrics.brier(P, y), rps=metrics.rps(P, y))
    # calibration pooled over the three outcome probabilities
    p = M.ravel(); hit = np.eye(3)[y].ravel()
    out["calibration_1x2"] = metrics.calibration(p, hit)
    o = res.dropna(subset=["m_over25"])
    if len(o):
        yo = o["over25"].to_numpy(int)
        mo = np.c_[o["p_over25"], 1 - o["p_over25"]]; ko = np.c_[o["m_over25"], 1 - o["m_over25"]]
        yc = 1 - yo   # class 0 = over
        out["n_ou"] = len(o)
        out["ou_model"] = dict(log_loss=metrics.log_loss(mo, yc), brier=metrics.brier(mo, yc))
        out["ou_market"] = dict(log_loss=metrics.log_loss(ko, yc), brier=metrics.brier(ko, yc))
        out["calibration_over25"] = metrics.calibration(o["p_over25"].to_numpy(), yo)
    return out


def fmt(s: dict) -> str:
    L = [f"1X2 on {s['n_1x2']} matches (Pinnacle close, Shin de-vigged)",
         f"{'':8}{'logloss':>9}{'brier':>8}{'RPS':>8}"]
    for k in ("model", "market", "naive"):
        v = s[k]; L.append(f"{k:8}{v['log_loss']:9.4f}{v['brier']:8.4f}{v['rps']:8.4f}")
    if "ou_model" in s:
        L.append(f"Over/Under 2.5 on {s['n_ou']} matches")
        for k in ("ou_model", "ou_market"):
            v = s[k]; L.append(f"{k:10}{v['log_loss']:9.4f}{v['brier']:8.4f}")
    bad = [b for b in s["calibration_1x2"] if not b["ok"]]
    L.append(f"1X2 calibration: {len(bad)}/{len(s['calibration_1x2'])} bins outside 95% interval")
    for b in s["calibration_1x2"]:
        L.append(f"  bin {b['bin']}: n={b['n']:5d} pred={b['mean_pred']:.3f} obs={b['observed']:.3f} "
                 f"[{b['lo']:.3f},{b['hi']:.3f}] {'ok' if b['ok'] else 'OFF'}")
    return "\n".join(L)
