"""High-level entry points shared by the CLI and the API."""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as C
from .explain import describe_plan
from .forecast import MA7, MLForecaster, Oracle, bank_group_shares, fit_dispersion
from .optimizer import group_split, plan_transfers
from .simulator import simulate, state_on
from .world import Scenario, World, build_world


@lru_cache(maxsize=4)
def forecaster(name: str = "ml"):
    """'ml' (trained model), 'ma7' (baseline) or 'oracle' (perfect foresight, for upper bounds)."""
    if name == "ml":
        return MLForecaster.load()
    w = build_world()
    t0, t1 = w.idx("2023-01-01"), w.idx("2023-12-24")
    f = {"ma7": MA7, "oracle": Oracle}[name]()
    f.k = fit_dispersion(f, w, t0, t1)
    if name == "oracle":
        f.k = np.minimum(f.k, 50.0)
    return f


def todays_plan(date: str, sc: Scenario = Scenario(), history_policy: str = "isolated",
                overrides: dict | None = None, forecaster_name: str = "ml") -> dict:
    """Recommended transfers for the morning of `date`.

    The network state comes from simulating the previous weeks under `history_policy`
    (default: banks working on their own, i.e. what the city looks like today).
    `overrides` lets a user type in real stock: {"SMS": {"PLT": 12, "O+": 30}, ...}.
    """
    w = build_world(sc)
    t = w.idx(date)
    inv = state_on(w, date, history_policy, forecaster(forecaster_name) if history_policy == "raktsetu" else None)
    if overrides:
        inv = apply_overrides(w, inv, overrides)
    f = forecaster(forecaster_name)
    mu = group_split(f.window(w, t, t + 1)[0], bank_group_shares(w, t))
    k = np.array([f.k[0]] * 8 + [f.k[1]])
    plan = plan_transfers(inv, mu, k, w.drive_min, vans=sc.vans)
    return describe_plan(w, plan, str(pd.Timestamp(date).date()))


def apply_overrides(w: World, inv: np.ndarray, overrides: dict) -> np.ndarray:
    """Replace a bank's stock of a product with a typed-in count, keeping the age profile (or assuming fresh-ish)."""
    inv = inv.copy()
    for short, skus in overrides.items():
        b = w.bank_index(short)
        for sku, n in skus.items():
            s = C.SKUS.index(sku)
            cur = inv[b, s]
            n = max(0, int(n))
            if cur.sum() > 0:
                scaled = np.floor(cur / cur.sum() * n)
                scaled[np.argmax(cur)] += n - scaled.sum()
            else:
                scaled = np.zeros_like(cur)
                scaled[2] = n
            inv[b, s] = scaled
    return inv


def compare_policies(start: str, end: str, sc: Scenario = Scenario(), forecaster_name: str = "ml",
                     policies=("isolated", "reactive", "raktsetu"), keep=False, progress=None) -> dict:
    w = build_world(sc)
    out = {}
    for n, p in enumerate(policies):
        f = forecaster(forecaster_name) if p == "raktsetu" else None
        cb = (lambda x, n=n: progress((n + x) / len(policies))) if progress else None
        out[p] = simulate(w, start, end, p, f, progress=cb)
    return {"world": w, "results": out} if keep else {p: r.kpis(w.banks, w.drive_km) for p, r in out.items()}
