"""Daily transfer planner: which units should move between which blood banks this morning.

Given each bank's stock (by blood group and age) and a demand forecast, it
  1. projects each bank's need over the next few days at a chosen service level,
  2. projects which units will expire unused (first-expiry-first-out),
  3. solves a small integer programme (OR-Tools CP-SAT) that moves units from banks
     with surplus or expiring stock to banks heading for a shortage, under a limit on
     van trips and box capacity, trading off shortage avoided, waste avoided and travel.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import NormalDist

import numpy as np
from ortools.sat.python import cp_model

from . import config as C

SHELF = np.array([C.SHELF_DAYS["RBC"]] * 8 + [C.SHELF_DAYS["PLT"]])
HORIZON = np.array([C.PLAN_HORIZON["RBC"]] * 8 + [C.PLAN_HORIZON["PLT"]])
AT_RISK_WINDOW = np.array([7] * 8 + [3])


@dataclass
class Transfer:
    src: int
    dst: int
    sku: int
    units: int


@dataclass
class Plan:
    transfers: list[Transfer]
    need: np.ndarray        # (B, S) units short of target
    give: np.ndarray        # (B, S) units a bank can spare
    at_risk: np.ndarray     # (B, S) units expected to expire unused within the window
    target: np.ndarray      # (B, S) protected demand over the horizon
    expected: np.ndarray    # (B, S) mean demand over the horizon
    stock: np.ndarray       # (B, S)
    trips: list[tuple[int, int]] = field(default_factory=list)
    status: str = ""
    objective: float = 0.0


def take_oldest(arr: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Remove up to n units from the oldest end of the last axis. Returns the amount taken per age.

    arr: (..., A) counts by age (index = age); n: (...) units wanted.
    """
    rev = arr[..., ::-1]
    before = np.cumsum(rev, axis=-1) - rev
    take_rev = np.clip(n[..., None] - before, 0, rev)
    return take_rev[..., ::-1]


def project_at_risk(stock: np.ndarray, daily_mu: np.ndarray) -> np.ndarray:
    """Units that will expire unused within AT_RISK_WINDOW days if demand runs at daily_mu (B, S)."""
    inv = stock.astype(float).copy()
    risk = np.zeros(inv.shape[:2])
    for d in range(int(AT_RISK_WINDOW.max())):
        inv -= take_oldest(inv, daily_mu)
        inv[..., 1:] = inv[..., :-1].copy()
        inv[..., 0] = 0
        for s in range(inv.shape[1]):
            if d < AT_RISK_WINDOW[s]:
                risk[:, s] += inv[:, s, SHELF[s]:].sum(axis=-1)
            inv[:, s, SHELF[s]:] = 0
    return np.floor(risk + 1e-9)


def sku_weight(s: int) -> float:
    if s == C.PLT:
        return C.W_UNIT["PLT"]
    return C.W_UNIT["RBC_NEG"] if C.SKUS[s].endswith("-") else C.W_UNIT["RBC_POS"]


def plan_transfers(
    stock_by_age: np.ndarray,   # (B, S, A)
    mu: np.ndarray,             # (B, S, H) forecast mean daily demand for the next H days
    k: np.ndarray,              # (S,) negative-binomial dispersion
    drive_min: np.ndarray,      # (B, B)
    vans: int = C.VANS,
    quantile: float = C.SERVICE_QUANTILE,
    time_limit_s: float = C.SOLVER_TIME_LIMIT_S,
) -> Plan:
    B, S, _ = stock_by_age.shape
    z = NormalDist().inv_cdf(quantile)
    stock = stock_by_age.sum(axis=-1)

    expected = np.zeros((B, S))
    target = np.zeros((B, S))
    for s in range(S):
        h = HORIZON[s]
        m = mu[:, s, :h]
        expected[:, s] = m.sum(axis=1)
        var = (m + m**2 / k[s]).sum(axis=1)
        target[:, s] = expected[:, s] + z * np.sqrt(var)

    at_risk = project_at_risk(stock_by_age, mu[:, :, 0])
    need = np.maximum(0, np.ceil(target - stock - 1e-9))
    surplus = np.maximum(0, np.floor(stock - target + 1e-9))
    give = np.where(need > 0, 0, np.maximum(surplus, np.minimum(at_risk, stock)))

    plan = Plan([], need, give, at_risk, target, expected, stock)
    max_trips = vans * C.TRIPS_PER_VAN
    if max_trips <= 0 or need.sum() == 0 or give.sum() == 0:
        plan.status = "nothing to move"
        return plan

    model = cp_model.CpModel()
    x: dict[tuple[int, int, int], cp_model.IntVar] = {}
    ub_of: dict[tuple[int, int, int], int] = {}
    for s in range(S):
        gi = np.nonzero(give[:, s])[0]
        for j in np.nonzero(need[:, s])[0]:
            # only the nearest few banks with spare stock are realistic suppliers
            near = [i for i in gi[np.argsort(drive_min[gi, j])] if i != j and drive_min[i, j] <= C.MAX_DRIVE_MIN]
            for i in near[: C.CANDIDATE_SUPPLIERS]:
                ub = int(min(give[i, s], need[j, s], C.BOX_CAPACITY))
                x[i, j, s] = model.NewIntVar(0, ub, f"x_{i}_{j}_{s}")
                ub_of[i, j, s] = ub
    if not x:
        plan.status = "no feasible pairs"
        return plan

    by_pair, by_out, by_in = defaultdict(list), defaultdict(list), defaultdict(list)
    for (i, j, s), v in x.items():
        by_pair[i, j].append(v)
        by_out[i, s].append(v)
        by_in[j, s].append(v)
    y = {p: model.NewBoolVar(f"y_{p[0]}_{p[1]}") for p in by_pair}
    for p, vs in by_pair.items():
        model.Add(sum(vs) <= C.BOX_CAPACITY * y[p])
    for key, v in x.items():  # strong linking: no units on an arc without a trip (tightens the LP bound)
        model.Add(v <= ub_of[key] * y[key[0], key[1]])
    model.Add(sum(y.values()) <= max_trips)
    for (i, s), vs in by_out.items():
        model.Add(sum(vs) <= int(give[i, s]))
    for (j, s), vs in by_in.items():
        model.Add(sum(vs) <= int(need[j, s]))

    # Units rescued from expiry: r[i,s] <= at_risk and <= what leaves the bank.
    r = {}
    for (i, s), vs in by_out.items():
        if at_risk[i, s] > 0:
            r[i, s] = model.NewIntVar(0, int(at_risk[i, s]), f"r_{i}_{s}")
            model.Add(r[i, s] <= sum(vs))

    SCALE = 100
    obj = []
    obj += [int(SCALE * sku_weight(s)) * v for (_, _, s), v in x.items()]
    obj += [int(SCALE * C.W_EXPIRY_SAVED) * v for v in r.values()]
    obj += [-int(SCALE * (C.TRIP_FIXED_COST + C.TRIP_COST_PER_MIN * drive_min[i, j])) * yv for (i, j), yv in y.items()]
    model.Maximize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.relative_gap_limit = C.SOLVER_GAP
    solver.parameters.num_workers = C.SOLVER_WORKERS
    solver.parameters.random_seed = 0
    st = solver.Solve(model)
    plan.status = solver.StatusName(st)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return plan
    plan.objective = solver.ObjectiveValue() / SCALE
    for (i, j, s), v in x.items():
        n = solver.Value(v)
        if n > 0:
            plan.transfers.append(Transfer(int(i), int(j), int(s), int(n)))
    plan.trips = sorted({(t.src, t.dst) for t in plan.transfers})
    return plan


def group_split(mu_product: np.ndarray, shares: np.ndarray) -> np.ndarray:
    """(B, 2, H) product-level forecast -> (B, S, H) SKU-level using each bank's group mix (B, 8)."""
    B, _, H = mu_product.shape
    out = np.zeros((B, len(C.SKUS), H))
    out[:, :8, :] = mu_product[:, 0, None, :] * shares[:, :, None]
    out[:, C.PLT, :] = mu_product[:, 1, :]
    return out


def dispersion_vector(k_rbc: float, k_plt: float) -> np.ndarray:
    return np.array([k_rbc] * 8 + [k_plt], dtype=float)

