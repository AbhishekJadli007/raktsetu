"""RaktSetu command line.

  python -m raktsetu plan --date 2026-10-10                 # today's recommended transfers, with reasons
  python -m raktsetu radar --date 2024-08-20                # 4-week platelet surge warning
  python -m raktsetu simulate --start 2024-08-15 --end 2024-11-30 --separator-failure BMCHRC:2024-09-01:2024-09-30
  python -m raktsetu train | evaluate [--quick] | generate | fetch
"""
from __future__ import annotations

import argparse
import json
import sys


def _scenario(a):
    from .world import Scenario

    surge = tuple((b, d, int(u)) for b, d, u in (s.split(":") for s in (a.surge or [])))
    return Scenario(
        seed=a.seed, dengue_scale=a.dengue_scale, kappa=a.kappa, donation_change=a.donation_change,
        separator_failure=tuple(tuple(s.split(":")) for s in (a.separator_failure or [])),
        collection_halt=tuple(tuple(s.split(":")) for s in (a.collection_halt or [])),
        surge=surge, vans=a.vans,
    )


def _add_scenario_args(p):
    from . import config as C
    g = p.add_argument_group("scenario")
    g.add_argument("--seed", type=int, default=C.SEED)
    g.add_argument("--dengue-scale", type=float, default=1.0, help="multiply the real dengue-year severity")
    g.add_argument("--kappa", type=float, default=C.DENGUE_PLT_KAPPA, help="peak platelet multiplier in a median year")
    g.add_argument("--donation-change", type=float, default=0.0, help="e.g. -0.3 = walk-in donations fall 30%%")
    g.add_argument("--separator-failure", action="append", metavar="BANK:START:END", help="platelet production stops")
    g.add_argument("--collection-halt", action="append", metavar="BANK:START:END", help="bank collects nothing")
    g.add_argument("--surge", action="append", metavar="BANK:DATE:UNITS", help="mass-casualty red-cell demand")
    g.add_argument("--vans", type=int, default=C.VANS)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="raktsetu", description="Predictive blood sharing for Jaipur's blood banks")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("fetch", help="re-download real inputs (OSM, OSRM, Open-Meteo)")
    sub.add_parser("generate", help="write the synthetic world to data/generated/")
    sub.add_parser("train", help="train the demand forecaster and surge radar")
    p = sub.add_parser("precompute", help="save the web demo flows to artifacts/cache/ (for small servers)")
    p.add_argument("--fresh", action="store_true", help="recompute everything (after changing the engine)")
    p = sub.add_parser("evaluate", help="full evaluation -> docs/EVALUATION.md")
    p.add_argument("--quick", action="store_true", help="1 seed instead of 5 (~5 min)")

    p = sub.add_parser("plan", help="recommended transfers for one morning")
    p.add_argument("--date", default="2026-10-10")
    p.add_argument("--history", default="isolated", choices=["isolated", "reactive", "raktsetu"],
                   help="how banks behaved in the weeks before (sets today's stock)")
    p.add_argument("--set-stock", action="append", metavar="BANK:SKU:UNITS", help="type in real stock, e.g. SMS:PLT:4")
    p.add_argument("--json", action="store_true")
    _add_scenario_args(p)

    p = sub.add_parser("radar", help="4-week platelet surge warning")
    p.add_argument("--date", default="2026-10-10")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("simulate", help="compare policies over a date range")
    p.add_argument("--start", default="2024-08-15")
    p.add_argument("--end", default="2024-11-30")
    p.add_argument("--forecaster", default="ml", choices=["ml", "ma7", "oracle"])
    p.add_argument("--json", action="store_true")
    _add_scenario_args(p)

    a = ap.parse_args(argv)

    if a.cmd == "fetch":
        import runpy
        from .config import ROOT
        runpy.run_path(str(ROOT / "data" / "fetch_real_data.py"), run_name="__main__")

    elif a.cmd == "generate":
        import runpy
        from .config import ROOT
        runpy.run_path(str(ROOT / "data" / "generate.py"), run_name="__main__")

    elif a.cmd == "train":
        from . import forecast, surge
        from .world import build_world
        w = build_world()
        print("Training demand forecaster (train 2016-2022, validate 2023) ...")
        ml, info = forecast.train(w)
        ml.save()
        print(f"  saved artifacts/forecaster.joblib  {info}  dispersion k={ml.k.round(2).tolist()}")
        m = forecast.evaluate_forecasters(w, ml)
        forecast.save_metrics(m)
        print("Training surge radar ...")
        surge.train(w)
        surge.save_eval(surge.evaluate(w))
        print("  saved artifacts/surge_radar.joblib")

    elif a.cmd == "precompute":
        from api.main import precompute
        precompute(fresh=a.fresh)

    elif a.cmd == "evaluate":
        from .evaluate import run
        run(quick=a.quick)

    elif a.cmd == "plan":
        from .engine import todays_plan
        from .explain import format_text
        overrides = {}
        for s in a.set_stock or []:
            b, sku, n = s.split(":")
            overrides.setdefault(b, {})[sku] = int(n)
        d = todays_plan(a.date, _scenario(a), a.history, overrides or None)
        print(json.dumps(d, indent=2) if a.json else format_text(d))

    elif a.cmd == "radar":
        from .surge import radar
        from .world import build_world
        r = radar(build_world(), a.date)
        if a.json:
            print(json.dumps(r, indent=2))
        else:
            print(f"Platelet surge radar for {r['date']}  [{r['level'].upper()}]")
            print(f"  now: ~{r['current_demand_per_day']}/day requested, ~{r['current_production_per_day']}/day produced")
            for wk in r["weeks"]:
                print(f"  week of {wk['starts']}: ~{wk['expected_per_day']}/day  (80% band {wk['low']}-{wk['high']})")
            print(f"  {r['action']}")
            print(f"  why: {r['driver']}")

    elif a.cmd == "simulate":
        from .engine import compare_policies
        k = compare_policies(a.start, a.end, _scenario(a), a.forecaster)
        if a.json:
            print(json.dumps(k, indent=2))
        else:
            cols = [("rbc_fill_rate", "RBC fill", "%"), ("plt_fill_rate", "PLT fill", "%"), ("rbc_wastage_rate", "RBC waste", "%"),
                    ("plt_wastage_rate", "PLT waste", "%"), ("total_unmet", "unmet", ""), ("total_expired", "expired", ""),
                    ("total_trips", "trips", ""), ("total_km", "km", "")]
            print(f"{'policy':10s} " + " ".join(f"{c[1]:>10s}" for c in cols))
            for p, v in k.items():
                print(f"{p:10s} " + " ".join(f"{100 * v[c[0]]:9.1f}%" if c[2] == "%" else f"{v[c[0]]:10,.0f}" for c in cols))


if __name__ == "__main__":
    main()
