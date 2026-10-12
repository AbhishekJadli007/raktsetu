"""Demand forecasting: a gradient-boosted model that uses lagged rainfall, vs. simple baselines.

Each morning t we forecast, for every bank and product (red cells, platelets), the daily
requests for days t .. t+H-1 using only information available by the end of day t-1.

Baselines (the pack asks for these, and they are what blood banks effectively use today):
  * MA7     - average of the last 7 days ("plan on what we used last week")
  * SNAIVE  - same weekday last week
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config as C
from .world import World

H_MAX = max(C.PLAN_HORIZON.values())
PRODUCTS = ["RBC", "PLT"]
FEATURES = [
    "bank", "product", "h", "dow", "doy_sin", "doy_cos",
    "lag1", "ma7", "ma28", "ma91", "ma7_prev", "trend",
    "city_ma7", "city_ma28", "city_trend",
    "rain_0_14", "rain_14_28", "rain_28_56", "rain_56_84", "temp_14", "temp_28_56", "hum_14",
]
WEATHER_FEATURES = ["rain_0_14", "rain_14_28", "rain_28_56", "rain_56_84", "temp_14", "temp_28_56", "hum_14"]
MODEL_PATH = C.ARTIFACTS / "forecaster.joblib"
METRICS_PATH = C.ARTIFACTS / "forecast_metrics.json"


def product_demand(w: World) -> np.ndarray:
    """(T, B, 2): total red-cell requests and platelet requests."""
    return np.stack([w.demand[:, :, :8].sum(-1), w.demand[:, :, C.PLT]], axis=-1).astype(float)


def _trailing_mean(x: np.ndarray, n: int, offset: int = 0) -> np.ndarray:
    """Mean of x[t-offset-n : t-offset] along axis 0 (NaN where incomplete). x: (T, ...)."""
    cs = np.cumsum(np.concatenate([np.zeros((1,) + x.shape[1:]), x]), axis=0)
    out = np.full(x.shape, np.nan)
    t = np.arange(x.shape[0])
    hi, lo = t - offset, t - offset - n
    ok = lo >= 0
    out[ok] = (cs[hi[ok]] - cs[lo[ok]]) / n
    return out


def _weather_windows(w: World) -> pd.DataFrame:
    """Weather aggregates known on the morning of each date (windows end yesterday)."""
    wx = w.weather
    rain = wx["rain_mm"].fillna(0)
    temp = wx["temp_mean_c"]
    hum = wx["humidity_pct"]
    y_rain = rain.shift(1)
    cs = y_rain.fillna(0).cumsum()

    def rsum(a, b):  # rain over [t-b, t-a)
        return cs.shift(a) - cs.shift(b) if a else cs - cs.shift(b)

    df = pd.DataFrame({
        "rain_0_14": rsum(0, 14),
        "rain_14_28": rsum(14, 28),
        "rain_28_56": rsum(28, 56),
        "rain_56_84": rsum(56, 84),
        "temp_14": temp.shift(1).rolling(14).mean(),
        "temp_28_56": temp.shift(29).rolling(28).mean(),
        "hum_14": hum.shift(1).rolling(14).mean(),
    })
    return df.reindex(w.dates)


@dataclass
class FeatureCube:
    """Per-origin features for all banks/products; expanded to horizons on demand."""
    origin_feats: dict[str, np.ndarray]  # each (T, B, 2)
    weather: pd.DataFrame


def feature_cube(w: World) -> FeatureCube:
    D = product_demand(w)
    city = D.sum(axis=1, keepdims=True).repeat(D.shape[1], axis=1)
    lag1 = np.full(D.shape, np.nan)
    lag1[1:] = D[:-1]
    ma7, ma28, ma91 = _trailing_mean(D, 7), _trailing_mean(D, 28), _trailing_mean(D, 91)
    ma7_prev = _trailing_mean(D, 7, offset=7)
    c7, c28 = _trailing_mean(city, 7), _trailing_mean(city, 28)
    with np.errstate(divide="ignore", invalid="ignore"):
        trend = ma7 / np.maximum(ma28, 0.5)
        city_trend = c7 / np.maximum(c28, 0.5)
    feats = {
        "lag1": lag1, "ma7": ma7, "ma28": ma28, "ma91": ma91, "ma7_prev": ma7_prev, "trend": trend,
        "city_ma7": c7 / D.shape[1], "city_ma28": c28 / D.shape[1], "city_trend": city_trend,
    }
    return FeatureCube(feats, _weather_windows(w))


def design_matrix(w: World, cube: FeatureCube, origins: np.ndarray, with_target: bool = True) -> pd.DataFrame:
    """Rows = (origin t, bank, product, horizon h). Platelets only use h < PLAN_HORIZON['PLT']."""
    T, B = len(w.dates), w.B
    D = product_demand(w) if with_target else None
    parts = []
    for p, prod in enumerate(PRODUCTS):
        for h in range(C.PLAN_HORIZON[prod]):
            tt = origins[origins + h < T] if with_target else origins
            n = len(tt)
            tgt_day = np.minimum(tt + h, T - 1)
            dts = w.dates[tgt_day]
            doy = dts.dayofyear.to_numpy()
            block = {
                "t": np.repeat(tt, B), "bank": np.tile(np.arange(B), n), "product": p, "h": h,
                "dow": np.repeat(dts.dayofweek.to_numpy(), B),
                "doy_sin": np.repeat(np.sin(2 * np.pi * doy / 365.25), B),
                "doy_cos": np.repeat(np.cos(2 * np.pi * doy / 365.25), B),
            }
            for name, arr in cube.origin_feats.items():
                block[name] = arr[tt, :, p].reshape(-1)
            for name in WEATHER_FEATURES:
                block[name] = np.repeat(cube.weather[name].to_numpy()[tt], B)
            if with_target:
                block["y"] = D[tt + h, :, p].reshape(-1)
            parts.append(pd.DataFrame(block))
    return pd.concat(parts, ignore_index=True)


# ------------------------------------------------------------------ forecasters
class Forecaster:
    name = "base"
    k = np.array([C.NB_K["RBC"], C.NB_K["PLT"]])  # overwritten by fit_dispersion

    def window(self, w: World, t0: int, t1: int) -> np.ndarray:
        """Forecast mean daily demand: (t1-t0, B, 2, H_MAX) for origins t0..t1-1."""
        raise NotImplementedError


class MA7(Forecaster):
    name = "MA7"

    def window(self, w, t0, t1):
        D = product_demand(w)
        ma = _trailing_mean(D, 7)[t0:t1]
        return np.repeat(np.nan_to_num(ma)[..., None], H_MAX, axis=-1)


class SeasonalNaive(Forecaster):
    name = "Same weekday last week"

    def window(self, w, t0, t1):
        D = product_demand(w)
        out = np.zeros((t1 - t0, w.B, 2, H_MAX))
        for h in range(H_MAX):
            src = np.arange(t0, t1) + h - 7  # h < 7, so always in the past
            out[..., h] = D[np.clip(src, 0, None)]
        return out


class Oracle(Forecaster):
    """Knows the future exactly. Not deployable: an upper bound for the planner."""
    name = "Oracle"

    def window(self, w, t0, t1):
        D = product_demand(w)
        T = len(w.dates)
        out = np.zeros((t1 - t0, w.B, 2, H_MAX))
        for h in range(H_MAX):
            out[..., h] = D[np.minimum(np.arange(t0, t1) + h, T - 1)]
        return out


class MLForecaster(Forecaster):
    name = "RaktSetu ML"

    def __init__(self, model: HistGradientBoostingRegressor | None = None, k=None):
        self.model = model
        if k is not None:
            self.k = np.asarray(k, dtype=float)

    def window(self, w, t0, t1):
        cube = feature_cube(w)
        X = design_matrix(w, cube, np.arange(t0, t1), with_target=False)
        pred = np.clip(self.model.predict(X[FEATURES]), 0, None)
        out = np.zeros((t1 - t0, w.B, 2, H_MAX))
        out[X.t.to_numpy() - t0, X.bank.to_numpy(), X["product"].to_numpy(), X.h.to_numpy()] = pred
        # Platelet horizon is shorter; pad beyond it with the last forecast.
        hp = C.PLAN_HORIZON["PLT"]
        out[:, :, 1, hp:] = out[:, :, 1, hp - 1: hp]
        return out

    def save(self, path=MODEL_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "k": self.k.tolist(), "features": FEATURES}, path)

    @classmethod
    def load(cls, path=MODEL_PATH) -> "MLForecaster":
        d = joblib.load(path)
        return cls(d["model"], d["k"])


def fit_dispersion(f: Forecaster, w: World, t0: int, t1: int) -> np.ndarray:
    """Negative-binomial k per product from forecast residuals (var = mu + mu^2/k)."""
    mu = f.window(w, t0, t1)[..., 0]
    y = product_demand(w)[t0:t1]
    k = []
    for p in range(2):
        m, r = mu[..., p].ravel(), y[..., p].ravel()
        excess = np.mean((r - m) ** 2 - m)
        k.append(float(np.clip(np.mean(m**2) / max(excess, 1e-6), 1.0, 200.0)))
    return np.array(k)


def bank_group_shares(w: World, t: int, lookback: int = 365, prior: float = 50.0) -> np.ndarray:
    """Each bank's blood-group mix of requests over the past year, shrunk toward the population mix."""
    pop = np.array([C.GROUP_SHARE[g] for g in C.RBC_GROUPS])
    hist = w.demand[max(0, t - lookback):t, :, :8].sum(axis=0).astype(float)
    sh = (hist + prior * pop) / (hist.sum(axis=1, keepdims=True) + prior)
    return sh


# ------------------------------------------------------------------ training + evaluation
def train(w: World, verbose=True) -> tuple[MLForecaster, dict]:
    cube = feature_cube(w)
    first = int(np.argmax(w.dates >= pd.Timestamp(w.dates[0]) + pd.Timedelta(days=100)))
    t_train_end = w.idx(C.TRAIN_END)
    t_valid_end = w.idx(C.VALID_END)
    tr = design_matrix(w, cube, np.arange(first, t_train_end + 1 - H_MAX))
    va = design_matrix(w, cube, np.arange(t_train_end + 1, t_valid_end + 1 - H_MAX))
    tr, va = tr.dropna(subset=FEATURES), va.dropna(subset=FEATURES)
    cats = [FEATURES.index("bank"), FEATURES.index("product")]
    params = dict(loss="poisson", learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40,
                  l2_regularization=1.0, categorical_features=cats, early_stopping=False, random_state=C.SEED)
    # Pick the number of boosting rounds on the 2023 validation year (time split, never random).
    model = HistGradientBoostingRegressor(warm_start=True, **params)
    best, best_n = None, None
    for n in (100, 200, 300, 450, 600):
        model.set_params(max_iter=n)
        model.fit(tr[FEATURES], tr["y"])
        wape = _wape(va["y"], model.predict(va[FEATURES]))
        if verbose:
            print(f"  boosting rounds={n:4d}  validation WAPE={wape:.4f}")
        if best is None or wape < best - 1e-4:
            best, best_n = wape, n
    model = HistGradientBoostingRegressor(max_iter=best_n, **params)
    full = pd.concat([tr, va])
    model.fit(full[FEATURES], full["y"])
    f = MLForecaster(model)
    f.k = fit_dispersion(f, w, t_train_end + 1, t_valid_end + 1 - H_MAX)
    return f, {"iterations": best_n, "validation_wape": best, "train_rows": len(tr), "valid_rows": len(va)}


def _wape(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.abs(y - p).sum() / max(y.sum(), 1e-9))


def evaluate_forecasters(w: World, ml: MLForecaster) -> dict:
    """WAPE by product on the held-out test years, overall and in dengue season (Aug 15 - Nov 30)."""
    t0 = w.idx(f"{C.TEST_YEARS[0]}-01-01")
    t1 = min(w.idx(f"{C.TEST_YEARS[-1]}-12-31") + 1, len(w.dates)) - H_MAX
    D = product_demand(w)
    fs = {"RaktSetu ML": ml, "MA7 (last 7 days)": MA7(), "Same weekday last week": SeasonalNaive()}
    preds = {n: f.window(w, t0, t1) for n, f in fs.items()}
    dates = w.dates[t0:t1]
    season = ((dates.month == 8) & (dates.day >= 15)) | dates.month.isin([9, 10, 11])
    out = {"test_period": f"{dates[0].date()} to {dates[-1].date()}", "metric": "WAPE (lower is better)", "results": {}}
    for prod_i, prod in enumerate(PRODUCTS):
        for h in range(C.PLAN_HORIZON[prod]):
            y = D[t0 + h:t1 + h, :, prod_i]
            for n, P in preds.items():
                p = P[..., prod_i, h]
                key = f"{prod}|h+{h}"
                out["results"].setdefault(key, {})[n] = {
                    "all": round(_wape(y, p), 4),
                    "dengue_season": round(_wape(y[season], p[season]), 4),
                }
    return out


def permutation_importance_weather(w: World, ml: MLForecaster, n_repeats: int = 3) -> dict:
    """How much worse does the platelet forecast get if we scramble each feature? (dengue season, test years)."""
    cube = feature_cube(w)
    t0, t1 = w.idx(f"{C.TEST_YEARS[0]}-08-01"), w.idx(f"{C.TEST_YEARS[0]}-11-30")
    X = design_matrix(w, cube, np.arange(t0, t1)).dropna(subset=FEATURES)
    X = X[X["product"] == 1]
    base = _wape(X.y, ml.model.predict(X[FEATURES]))
    rng = np.random.default_rng(C.SEED)
    imp = {}
    for f in FEATURES:
        if f in ("product",):
            continue
        scores = []
        for _ in range(n_repeats):
            Xp = X[FEATURES].copy()
            Xp[f] = rng.permutation(Xp[f].to_numpy())
            scores.append(_wape(X.y, ml.model.predict(Xp)))
        imp[f] = round(float(np.mean(scores) - base), 4)
    return {"baseline_wape": round(base, 4), "increase_in_wape_when_shuffled": dict(sorted(imp.items(), key=lambda kv: -kv[1]))}


def save_metrics(d: dict):
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(d, indent=2))
