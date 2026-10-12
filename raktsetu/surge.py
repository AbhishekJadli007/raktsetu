"""Surge radar: city-wide platelet demand 1-4 weeks ahead, driven by lagged rainfall.

Moving stock between banks cannot fix a city-wide shortage. At the dengue peak the whole
network runs short of platelets, so the useful action is upstream: schedule platelet donors
and apheresis slots before the surge. That needs weeks of warning, which a 7-day average
cannot give but rainfall (which leads dengue by ~8 weeks) can.
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config as C
from .forecast import _trailing_mean, _wape, _weather_windows
from .world import World

WEEKS = 4
FEATURES = ["k", "ma7", "ma28", "trend", "doy_sin", "doy_cos",
            "rain_0_14", "rain_14_28", "rain_28_56", "rain_56_84", "temp_14", "temp_28_56", "hum_14"]
MODEL_PATH = C.MODEL_DIR / "surge_radar.joblib"


def city_platelets(w: World) -> np.ndarray:
    return w.demand[:, :, C.PLT].sum(axis=1).astype(float)


def _targets(P: np.ndarray, t: np.ndarray, k: int) -> np.ndarray:
    """Mean daily demand over week k ahead (days t+7(k-1) .. t+7k-1)."""
    cs = np.concatenate([[0.0], np.cumsum(P)])
    lo, hi = t + 7 * (k - 1), t + 7 * k
    ok = hi <= len(P)
    out = np.full(len(t), np.nan)
    out[ok] = (cs[hi[ok]] - cs[lo[ok]]) / 7
    return out


def design(w: World, origins: np.ndarray) -> pd.DataFrame:
    P = city_platelets(w)
    ma7, ma28 = _trailing_mean(P, 7), _trailing_mean(P, 28)
    wx = _weather_windows(w)
    rows = []
    for k in range(1, WEEKS + 1):
        doy = w.dates[np.minimum(origins + 7 * k - 4, len(P) - 1)].dayofyear.to_numpy()
        d = pd.DataFrame({
            "t": origins, "k": k, "ma7": ma7[origins], "ma28": ma28[origins],
            "trend": ma7[origins] / np.maximum(ma28[origins], 1),
            "doy_sin": np.sin(2 * np.pi * doy / 365.25), "doy_cos": np.cos(2 * np.pi * doy / 365.25),
            "y": _targets(P, origins, k),
        })
        for c in wx.columns:
            d[c] = wx[c].to_numpy()[origins]
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def baselines(w: World, origins: np.ndarray) -> dict[str, np.ndarray]:
    """Rows aligned with design(): persistence (MA7) and same week last year."""
    P = city_platelets(w)
    ma7 = _trailing_mean(P, 7)
    out = {"Current level persists (MA7)": [], "Same week last year": []}
    for k in range(1, WEEKS + 1):
        out["Current level persists (MA7)"].append(ma7[origins])
        out["Same week last year"].append(_targets(P, origins - 364, k))
    return {n: np.concatenate(v) for n, v in out.items()}


def train(w: World, verbose=True):
    t_first = 120
    t_tr, t_va = w.idx(C.TRAIN_END), w.idx(C.VALID_END)
    tr = design(w, np.arange(t_first, t_tr - 7 * WEEKS)).dropna()
    va = design(w, np.arange(t_tr + 1, t_va - 7 * WEEKS)).dropna()
    params = dict(loss="poisson", learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=30,
                  l2_regularization=1.0, random_state=C.SEED)
    best, best_n = None, None
    m = HistGradientBoostingRegressor(warm_start=True, **params)
    for n in (50, 100, 200, 300, 400):
        m.set_params(max_iter=n)
        m.fit(tr[FEATURES], tr.y)
        s = _wape(va.y, m.predict(va[FEATURES]))
        if verbose:
            print(f"  surge radar rounds={n:3d}  validation WAPE={s:.4f}")
        if best is None or s < best - 1e-4:
            best, best_n = s, n
    full = pd.concat([tr, va])
    model = HistGradientBoostingRegressor(max_iter=best_n, **params).fit(full[FEATURES], full.y)
    # Empirical 10-90% band of relative error per horizon, from the validation year.
    val_model = HistGradientBoostingRegressor(max_iter=best_n, **params).fit(tr[FEATURES], tr.y)
    rel = va.y / np.maximum(val_model.predict(va[FEATURES]), 1e-6)
    band = {int(k): [float(np.quantile(rel[va.k == k], 0.1)), float(np.quantile(rel[va.k == k], 0.9))] for k in range(1, WEEKS + 1)}
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "band": band, "rounds": best_n}, MODEL_PATH)
    return model, band


def load():
    d = joblib.load(MODEL_PATH)
    return d["model"], d["band"]


def evaluate(w: World) -> dict:
    model, _ = load()
    t0 = w.idx(f"{C.TEST_YEARS[0]}-01-01")
    t1 = min(w.idx(f"{C.TEST_YEARS[-1]}-12-31"), len(w.dates) - 1 - 7 * WEEKS)
    origins = np.arange(t0, t1)
    X = design(w, origins)
    preds = {"RaktSetu surge radar": model.predict(X[FEATURES]), **baselines(w, origins)}
    dates = w.dates[X.t.to_numpy()]
    ramp = ((dates.month == 7) & (dates.day >= 15)) | (dates.month == 8) | ((dates.month == 9) & (dates.day <= 30))
    out = {"test_period": f"{w.dates[t0].date()} to {w.dates[t1].date()}",
           "target": "mean daily city-wide platelet requests in week k ahead",
           "metric": "WAPE (lower is better)",
           "ramp_up_window": "forecasts issued 15 Jul - 30 Sep (as the dengue surge builds)",
           "results": {}}
    ok = ~np.isnan(X.y.to_numpy())
    for k in range(1, WEEKS + 1):
        m = (X.k.to_numpy() == k) & ok
        for name, p in preds.items():
            mm = m & ~np.isnan(p)
            out["results"].setdefault(f"week+{k}", {})[name] = {
                "all": round(_wape(X.y[mm], p[mm]), 4),
                "ramp_up": round(_wape(X.y[mm & ramp], p[mm & ramp]), 4),
            }
    return out


def radar(w: World, date: str) -> dict:
    """What the district coordinator sees: the next 4 weeks of platelet demand vs current production."""
    model, band = load()
    t = w.idx(date)
    X = design(w, np.array([t]))
    pred = model.predict(X[FEATURES])
    P = city_platelets(w)
    prod = w.collections[max(0, t - 14):t, :, C.PLT].sum(axis=1).mean()
    now = float(np.mean(P[max(0, t - 7):t]))
    weeks = []
    for k, p in zip(X.k, pred):
        lo, hi = band[int(k)]
        start = w.dates[t] + pd.Timedelta(days=7 * (int(k) - 1))
        weeks.append({"week": int(k), "starts": str(start.date()), "expected_per_day": round(float(p), 1),
                      "low": round(float(p * lo), 1), "high": round(float(p * hi), 1)})
    peak = max(weeks, key=lambda d: d["expected_per_day"])
    gap = peak["expected_per_day"] - prod
    if gap > 0.1 * prod:
        level = "alert" if gap > 0.35 * prod else "watch"
        action = (f"Expected platelet need of ~{peak['expected_per_day']:.0f}/day by the week of {peak['starts']} "
                  f"exceeds current production (~{prod:.0f}/day). Schedule ~{gap * 7:.0f} extra platelet units per week: "
                  f"donor drives at camp-running banks and apheresis slots at the large hospital banks.")
    else:
        level = "normal"
        action = "Platelet production is on track for the next 4 weeks. No extra drives needed."
    wx = w.weather
    d = pd.Timestamp(date)
    rain_8w = float(wx["rain_mm"].loc[d - pd.Timedelta(days=84): d - pd.Timedelta(days=28)].sum())
    return {"date": str(d.date()), "current_demand_per_day": round(now, 1), "current_production_per_day": round(float(prod), 1),
            "weeks": weeks, "level": level, "action": action,
            "driver": f"{rain_8w:.0f} mm of rain fell in Jaipur 4-12 weeks ago, the window that drives dengue transmission now."}


def save_eval(d: dict):
    (C.ARTIFACTS / "surge_metrics.json").write_text(json.dumps(d, indent=2))
