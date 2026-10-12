"""Day-by-day inventory simulation of the Jaipur blood network under different coordination policies.

Each simulated day:
  1. Morning   - the policy may plan transfers (RaktSetu); vans move units between banks.
  2. Daytime   - each bank serves its requests oldest-unit-first, substituting compatible red-cell groups.
  3. Emergency - a bank that ran short phones its nearest neighbours (today's practice).
  4. Evening   - donated units are added; everything ages one day; units past shelf life are discarded.

Policies:
  isolated   - every bank on its own (no sharing at all)
  reactive   - phone-around after a stock-out (how sharing works today)
  raktsetu   - forecast + optimised morning transfers, with the phone-around kept as a fallback
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C
from .forecast import Forecaster, bank_group_shares, product_demand
from .optimizer import SHELF, Plan, group_split, plan_transfers, take_oldest
from .world import World

A = int(SHELF.max()) + 1
POLICIES = ("isolated", "reactive", "raktsetu")


@dataclass
class SimResult:
    policy: str
    forecaster: str | None
    dates: pd.DatetimeIndex
    demand: np.ndarray       # (T, B, S)
    served: np.ndarray
    unmet: np.ndarray
    expired: np.ndarray
    collected: np.ndarray
    stock: np.ndarray        # (T, B, S) end-of-day stock
    transfers: list = field(default_factory=list)  # dicts: day, src, dst, sku, units, kind
    plans: dict = field(default_factory=dict)      # day index -> Plan (only if keep_plans)
    final_inventory: np.ndarray | None = None      # (B, S, A) at the start of the day after `end`

    def kpis(self, banks: pd.DataFrame | None = None, drive_km: np.ndarray | None = None) -> dict:
        def tot(a, sl):
            return int(a[:, :, sl].sum())
        rbc, plt = slice(0, 8), slice(8, 9)
        tr = pd.DataFrame(self.transfers) if self.transfers else pd.DataFrame(columns=["day", "src", "dst", "sku", "units", "kind"])
        out = {}
        for kind in ("planned", "emergency"):
            t = tr[tr.kind == kind]
            trips = t.groupby(["day", "src", "dst"]).size().reset_index() if len(t) else t
            km = float(sum(drive_km[r.src, r.dst] for r in trips.itertuples())) if (drive_km is not None and len(t)) else 0.0
            out[f"{kind}_trips"] = int(len(trips))
            out[f"{kind}_units_moved"] = int(t.units.sum()) if len(t) else 0
            out[f"{kind}_km"] = round(km, 1)
        d_r, d_p = tot(self.demand, rbc), tot(self.demand, plt)
        u_r, u_p = tot(self.unmet, rbc), tot(self.unmet, plt)
        e_r, e_p = tot(self.expired, rbc), tot(self.expired, plt)
        c_r, c_p = tot(self.collected, rbc), tot(self.collected, plt)
        return {
            "policy": self.policy,
            "forecaster": self.forecaster,
            "days": len(self.dates),
            "rbc_requests": d_r, "rbc_unmet": u_r, "rbc_fill_rate": round(1 - u_r / max(d_r, 1), 4),
            "plt_requests": d_p, "plt_unmet": u_p, "plt_fill_rate": round(1 - u_p / max(d_p, 1), 4),
            "rbc_expired": e_r, "rbc_wastage_rate": round(e_r / max(c_r, 1), 4),
            "plt_expired": e_p, "plt_wastage_rate": round(e_p / max(c_p, 1), 4),
            "total_unmet": u_r + u_p, "total_expired": e_r + e_p,
            **out,
            "total_trips": out["planned_trips"] + out["emergency_trips"],
            "total_km": round(out["planned_km"] + out["emergency_km"], 1),
        }


def initial_inventory(w: World, t: int, rng: np.random.Generator) -> np.ndarray:
    """Start each bank with ~6 days of red cells and ~2 days of platelets, ages spread evenly."""
    B, S = w.B, len(C.SKUS)
    inv = np.zeros((B, S, A))
    recent = w.demand[max(0, t - 28):t].mean(axis=0)  # (B, S)
    for s in range(S):
        days, max_age = (6, 28) if s < 8 else (2, 3)
        units = rng.poisson(recent[:, s] * days)
        for b in range(B):
            if units[b]:
                ages = rng.integers(1, max_age + 1, size=units[b])
                inv[b, s] += np.bincount(ages, minlength=A)[:A]
    return inv


def serve(inv: np.ndarray, dem: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Serve requests oldest-first; then red-cell substitution with compatible groups. Mutates inv."""
    take = take_oldest(inv, dem.astype(float))
    inv -= take
    served = take.sum(-1)
    unmet = dem - served
    order = ["O-", "A-", "B-", "AB-", "O+", "A+", "B+", "AB+"]  # fewest options first
    gi = {g: i for i, g in enumerate(C.RBC_GROUPS)}
    for g in order:
        r = gi[g]
        for donor in C.RBC_COMPATIBLE[g][1:]:
            u = unmet[:, r]
            if not u.any():
                break
            d = gi[donor]
            tk = take_oldest(inv[:, d, :], u)
            inv[:, d, :] -= tk
            n = tk.sum(-1)
            unmet[:, r] -= n
            served[:, r] += n
    return served, unmet


def move(inv: np.ndarray, src: int, dst: int, s: int, n: int) -> int:
    tk = take_oldest(inv[src, s][None, :], np.array([float(n)]))[0]
    inv[src, s] -= tk
    inv[dst, s] += tk
    return int(round(tk.sum()))


def emergency_phone_around(inv, unmet, served, recent_use, drive_min, day, log):
    """Today's practice: a bank that ran out calls its nearest neighbours, who lend only true spare stock."""
    B = inv.shape[0]
    for b, s in zip(*np.nonzero(unmet > 0)):
        need = int(unmet[b, s])
        order = [j for j in np.argsort(drive_min[b]) if j != b and drive_min[b, j] <= C.MAX_DRIVE_MIN]
        for j in order[: C.REACTIVE_NEIGHBOURS]:
            spare = int(inv[j, s].sum() - C.REACTIVE_COMFORT_DAYS * recent_use[j, s])
            if spare <= 0:
                continue
            got = move(inv, j, b, s, min(spare, need))
            if got:
                # units arrive and are issued straight away
                inv[b, s] -= take_oldest(inv[b, s][None, :], np.array([float(got)]))[0]
                unmet[b, s] -= got
                served[b, s] += got
                need -= got
                log.append({"day": day, "src": int(j), "dst": int(b), "sku": int(s), "units": got, "kind": "emergency"})
            if need <= 0:
                break
    return unmet, served


def simulate(
    w: World,
    start: str,
    end: str,
    policy: str = "raktsetu",
    forecaster: Forecaster | None = None,
    warmup_days: int = 42,
    quantile: float = C.SERVICE_QUANTILE,
    vans: int | None = None,
    keep_plans: bool = False,
    progress=None,
    initial: np.ndarray | None = None,
) -> SimResult:
    assert policy in POLICIES, policy
    if policy == "raktsetu" and forecaster is None:
        raise ValueError("raktsetu policy needs a forecaster")
    vans = w.scenario.vans if vans is None else vans
    t_start, t_end = w.idx(start), w.idx(end)
    t0 = max(120, t_start - warmup_days)
    rng = np.random.default_rng(w.scenario.seed + 7)
    inv = initial_inventory(w, t0, rng) if initial is None else initial.copy()
    B, S = w.B, len(C.SKUS)
    n = t_end - t0 + 1
    rec = {k: np.zeros((n, B, S)) for k in ("demand", "served", "unmet", "expired", "collected", "stock")}
    log: list[dict] = []
    plans: dict[int, Plan] = {}

    if policy == "raktsetu":
        mu_prod = forecaster.window(w, t0, t_end + 1)  # (n, B, 2, H)
        kvec = np.array([forecaster.k[0]] * 8 + [forecaster.k[1]])
        shares = bank_group_shares(w, t0)

    for k, t in enumerate(range(t0, t_end + 1)):
        day = w.dates[t]
        if policy == "raktsetu":
            mu = group_split(mu_prod[k], shares)
            plan = plan_transfers(inv, mu, kvec, w.drive_min, vans=vans, quantile=quantile)
            for tr in plan.transfers:
                got = move(inv, tr.src, tr.dst, tr.sku, tr.units)
                if got:
                    log.append({"day": k, "src": tr.src, "dst": tr.dst, "sku": tr.sku, "units": got, "kind": "planned"})
            if keep_plans:
                plans[k] = plan

        dem = w.demand[t].astype(float)
        served, unmet = serve(inv, dem)
        if policy in ("reactive", "raktsetu"):
            recent = w.demand[max(0, t - 7):t].mean(axis=0)
            unmet, served = emergency_phone_around(inv, unmet, served, recent, w.drive_min, k, log)

        inv[:, :, 0] += w.collections[t]
        inv[:, :, 1:] = inv[:, :, :-1].copy()
        inv[:, :, 0] = 0
        expired = np.zeros((B, S))
        for s in range(S):
            expired[:, s] = inv[:, s, SHELF[s]:].sum(-1)
            inv[:, s, SHELF[s]:] = 0

        rec["demand"][k], rec["served"][k], rec["unmet"][k] = dem, served, unmet
        rec["expired"][k], rec["collected"][k] = expired, w.collections[t]
        rec["stock"][k] = inv.sum(-1)
        if progress and k % 10 == 0:
            progress(k / n)

    # drop warm-up
    off = t_start - t0
    keep = slice(off, None)
    log = [dict(e, day=e["day"] - off) for e in log if e["day"] >= off]
    plans = {d - off: p for d, p in plans.items() if d >= off}
    return SimResult(
        policy=policy, forecaster=getattr(forecaster, "name", None), dates=w.dates[t_start:t_end + 1],
        transfers=log, plans=plans, final_inventory=inv, **{k: v[keep] for k, v in rec.items()},
    )


def state_on(w: World, date: str, policy: str = "isolated", forecaster: Forecaster | None = None,
             warmup_days: int = 60) -> np.ndarray:
    """Inventory (B, S, A) on the morning of `date`, after simulating the preceding weeks under `policy`."""
    prev = w.dates[w.idx(date) - 1]
    res = simulate(w, str(prev.date()), str(prev.date()), policy, forecaster, warmup_days=warmup_days)
    return res.final_inventory


__all__ = ["simulate", "state_on", "SimResult", "POLICIES", "product_demand"]
