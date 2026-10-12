"""Turn an optimiser plan into instructions a blood-bank coordinator can act on and check."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from . import config as C
from .optimizer import HORIZON, Plan, SHELF
from .world import World


def _days_of_cover(stock: np.ndarray, expected: np.ndarray, horizon: np.ndarray) -> np.ndarray:
    daily = expected / horizon
    return np.where(daily > 0, stock / np.maximum(daily, 1e-9), np.inf)


def describe_plan(w: World, plan: Plan, date: str) -> dict:
    banks = w.banks
    trips = defaultdict(list)
    for t in plan.transfers:
        trips[t.src, t.dst].append(t)

    cards = []
    for (i, j), items in sorted(trips.items(), key=lambda kv: -sum(t.units for t in kv[1])):
        lines, reasons = [], []
        for t in sorted(items, key=lambda t: -t.units):
            s, sku = t.sku, C.SKUS[t.sku]
            prod = "platelets" if s == C.PLT else f"{sku} red cells"
            lines.append({"sku": sku, "units": t.units})
            h = int(HORIZON[s])
            reasons.append(
                f"{banks.short[j]} holds {int(plan.stock[j, s])} {prod} but expects ~{plan.expected[j, s]:.0f} requests in the next "
                f"{h} days (protecting against up to {plan.target[j, s]:.0f})."
            )
            if plan.at_risk[i, s] > 0:
                reasons.append(
                    f"{banks.short[i]} has {int(plan.at_risk[i, s])} {prod} likely to expire unused within "
                    f"{'3' if s == C.PLT else '7'} days, so moving them saves units that would otherwise be discarded."
                )
            else:
                reasons.append(f"{banks.short[i]} keeps its own protected need and can spare {int(plan.give[i, s])} {prod}.")
        cards.append({
            "from": banks.short[i], "from_name": banks.name[i],
            "to": banks.short[j], "to_name": banks.name[j],
            "drive_min": round(float(w.drive_min[i, j]), 1), "drive_km": round(float(w.drive_km[i, j]), 1),
            "items": lines, "units": int(sum(t.units for t in items)),
            "reasons": list(dict.fromkeys(reasons)),
        })

    cover = _days_of_cover(plan.stock, plan.expected, HORIZON[None, :])
    status = []
    for b in range(w.B):
        rbc_stock = int(plan.stock[b, :8].sum())
        rbc_daily = float(plan.expected[b, :8].sum() / C.PLAN_HORIZON["RBC"])
        plt_daily = float(plan.expected[b, C.PLT] / C.PLAN_HORIZON["PLT"])
        short = [C.SKUS[s] for s in range(len(C.SKUS)) if plan.need[b, s] > 0]
        status.append({
            "bank": banks.short[b], "name": banks.name[b], "lat": float(banks.lat[b]), "lon": float(banks.lon[b]),
            "operator": banks.operator_type[b], "role": banks.role[b],
            "rbc_stock": rbc_stock, "rbc_days_cover": round(rbc_stock / max(rbc_daily, 1e-9), 1),
            "plt_stock": int(plan.stock[b, C.PLT]), "plt_days_cover": round(float(plan.stock[b, C.PLT]) / max(plt_daily, 1e-9), 1),
            "at_risk_units": int(plan.at_risk[b].sum()), "short_skus": short,
            "need_units": int(plan.need[b].sum()), "spare_units": int(plan.give[b].sum()),
            "stock_by_sku": {C.SKUS[s]: int(plan.stock[b, s]) for s in range(len(C.SKUS))},
            "min_cover_days": round(float(np.min(np.where(np.isfinite(cover[b]), cover[b], 99))), 1),
        })

    # Shortfalls the network cannot cover by moving stock: these need donors, not vans.
    inflow = np.zeros_like(plan.need)
    for t in plan.transfers:
        inflow[t.dst, t.sku] += t.units
    gap = np.maximum(0, plan.need - inflow)
    unresolved = []
    for b, s in sorted(zip(*np.nonzero(gap >= 2)), key=lambda bs: -gap[bs] * (3 if bs[1] == C.PLT else 1)):
        prod = "platelets" if s == C.PLT else f"{C.SKUS[s]} red cells"
        unresolved.append({
            "bank": banks.short[b], "sku": C.SKUS[s], "units": int(gap[b, s]),
            "action": (f"Arrange {int(gap[b, s])} more {prod} for {banks.short[b]} "
                       f"({'platelet donors or apheresis slots' if s == C.PLT else 'call registered donors'}): "
                       f"no bank within reach can spare them without risking its own patients."),
        })

    moved = sum(t.units for t in plan.transfers)
    rescued = int(sum(min(plan.at_risk[t.src, t.sku], t.units) for t in plan.transfers))
    summary = (
        f"{len(cards)} trips moving {moved} units today. "
        f"{int((plan.need > 0).sum())} bank-product combinations are below their protected level; "
        f"{int(plan.at_risk.sum())} units across the city are at risk of expiring unused."
        if cards else "No transfers needed today: every bank covers its protected need or no bank can spare stock."
    )
    return {
        "date": date, "summary": summary, "trips": cards, "banks": status, "unresolved": unresolved[:12],
        "totals": {"trips": len(cards), "units": moved, "units_rescued_from_expiry": rescued,
                   "km": round(sum(c["drive_km"] for c in cards), 1),
                   "at_risk_units": int(plan.at_risk.sum()), "short_positions": int((plan.need > 0).sum()),
                   "unresolved_units": int(gap.sum())},
        "solver_status": plan.status, "vans": w.scenario.vans, "max_trips": w.scenario.vans * C.TRIPS_PER_VAN,
        "shelf_days": {"RBC": int(SHELF[0]), "PLT": int(SHELF[C.PLT])},
    }


def format_text(d: dict) -> str:
    out = [f"RaktSetu transfer plan for {d['date']}", "=" * 60, d["summary"], ""]
    for n, c in enumerate(d["trips"], 1):
        items = ", ".join(f"{it['units']} x {it['sku']}" for it in c["items"])
        out.append(f"{n}. {c['from']} -> {c['to']}  ({c['drive_km']} km, ~{c['drive_min']:.0f} min)  {items}")
        for r in c["reasons"]:
            out.append(f"     - {r}")
    if d["unresolved"]:
        out += ["", "Needs donors, not vans:"] + [f"  ! {u['action']}" for u in d["unresolved"]]
    out.append("")
    out.append(f"{'bank':10s} {'RBC':>5s} {'RBC days':>9s} {'PLT':>5s} {'PLT days':>9s} {'at risk':>8s}  short")
    for b in sorted(d["banks"], key=lambda b: b["min_cover_days"]):
        out.append(f"{b['bank']:10s} {b['rbc_stock']:5d} {b['rbc_days_cover']:9.1f} {b['plt_stock']:5d} {b['plt_days_cover']:9.1f} "
                   f"{b['at_risk_units']:8d}  {', '.join(b['short_skus'])}")
    return "\n".join(out)
