"""Full evaluation: forecasts vs baselines, policies across seeds, sensitivity, reproducibility.

Writes artifacts/evaluation.json and docs/EVALUATION.md. Run:  python -m raktsetu evaluate
"""
from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np
import pandas as pd

from . import config as C
from . import surge
from .engine import forecaster
from .forecast import MLForecaster, _wape, evaluate_forecasters, permutation_importance_weather
from .simulator import simulate
from .world import Scenario, build_world

WINDOWS = {"2024 dengue season": ("2024-08-15", "2024-11-30"), "2025 full year": ("2025-01-01", "2025-12-31")}
VARIANTS = [("isolated", None), ("reactive", None), ("raktsetu", "ma7"), ("raktsetu", "ml"), ("raktsetu", "oracle")]
LABEL = {
    ("isolated", None): "Isolated banks",
    ("reactive", None): "Phone-around (today)",
    ("raktsetu", "ma7"): "RaktSetu + 7-day average",
    ("raktsetu", "ml"): "RaktSetu + ML forecast",
    ("raktsetu", "oracle"): "RaktSetu + perfect forecast (bound)",
}
KEYS = ["rbc_fill_rate", "plt_fill_rate", "rbc_wastage_rate", "plt_wastage_rate", "rbc_unmet", "plt_unmet",
        "rbc_expired", "plt_expired", "planned_trips", "emergency_trips", "total_km"]
SENSITIVITY = {
    "kappa": ("Dengue platelet peak (x baseline - 1)", [1.5, 2.5, 4.0]),
    "collection_ratio": ("Collection / demand", [0.98, 1.08, 1.18]),
    "vans": ("Vans available", [1, 2, 3]),
    "quantile": ("Service quantile protected", [0.7, 0.8, 0.9]),
}


def noise_floor(w) -> dict:
    """WAPE of the TRUE expected demand: no forecast can beat this on noisy daily counts."""
    t0 = w.idx(f"{C.TEST_YEARS[0]}-01-01")
    t1 = w.idx(f"{C.TEST_YEARS[-1]}-12-31")
    y = np.stack([w.demand[t0:t1, :, :8].sum(-1), w.demand[t0:t1, :, C.PLT]], -1)
    return {p: round(_wape(y[..., i], w.mu_true[t0:t1, :, i]), 4) for i, p in enumerate(["RBC", "PLT"])}


def run(quick: bool = False, log=print) -> dict:
    t_start = time.time()
    w = build_world()
    ml = MLForecaster.load()
    report = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "quick": quick}

    log("1/5 forecast accuracy (held-out 2024-2025)")
    fm = evaluate_forecasters(w, ml)
    fm["noise_floor"] = noise_floor(w)
    fm["note"] = "noise_floor = WAPE of the true expected demand; daily counts per bank are inherently noisy."
    report["forecast"] = fm
    report["feature_importance"] = permutation_importance_weather(w, ml)

    log("2/5 surge radar (city-wide platelets, 1-4 weeks ahead)")
    report["surge_radar"] = surge.evaluate(w)

    seeds = [C.SEED] if quick else [42, 43, 44, 45, 46]
    log(f"3/5 policies x {len(seeds)} seeds x {len(WINDOWS)} windows")
    rows = []
    for seed in seeds:
        ws = build_world(Scenario(seed=seed))
        for wname, (a, b) in WINDOWS.items():
            for pol, fc in VARIANTS:
                k = simulate(ws, a, b, pol, forecaster(fc) if fc else None).kpis(ws.banks, ws.drive_km)
                rows.append({"seed": seed, "window": wname, "variant": LABEL[pol, fc], **{x: k[x] for x in KEYS}})
            log(f"   seed {seed} {wname} done ({time.time() - t_start:.0f}s)")
    df = pd.DataFrame(rows)
    report["policy_runs"] = rows
    agg = df.groupby(["window", "variant"], sort=False)[KEYS].agg(["mean", "std"]).round(4)
    report["policy_summary"] = {
        f"{wn}|{vn}": {k: {"mean": float(agg.loc[(wn, vn), (k, "mean")]), "std": float(np.nan_to_num(agg.loc[(wn, vn), (k, "std")]))} for k in KEYS}
        for wn, vn in agg.index
    }

    log("4/5 sensitivity (2024 dengue season)")
    sens_seeds = [42] if quick else [42, 43, 44]
    a, b = WINDOWS["2024 dengue season"]
    sens = []
    for param, (label, values) in SENSITIVITY.items():
        for v in values:
            for seed in sens_seeds:
                kw = {} if param == "quantile" else {param: v}
                ws = build_world(Scenario(seed=seed, **kw))
                q = v if param == "quantile" else C.SERVICE_QUANTILE
                re = simulate(ws, a, b, "reactive").kpis(ws.banks, ws.drive_km)
                rs = simulate(ws, a, b, "raktsetu", forecaster("ml"), quantile=q).kpis(ws.banks, ws.drive_km)
                sens.append({"param": param, "label": label, "value": v, "seed": seed,
                             **{f"reactive_{x}": re[x] for x in KEYS}, **{f"raktsetu_{x}": rs[x] for x in KEYS}})
            log(f"   {param}={v} done ({time.time() - t_start:.0f}s)")
    report["sensitivity_runs"] = sens

    log("5/5 reproducibility (same run twice; parallel solver)")
    ws = build_world()
    r1 = simulate(ws, a, b, "raktsetu", forecaster("ml")).kpis(ws.banks, ws.drive_km)
    r2 = simulate(ws, a, b, "raktsetu", forecaster("ml")).kpis(ws.banks, ws.drive_km)
    report["reproducibility"] = {k: [r1[k], r2[k]] for k in ("rbc_unmet", "plt_unmet", "rbc_expired", "plt_expired", "planned_trips")}

    report["runtime_s"] = round(time.time() - t_start, 1)
    C.ARTIFACTS.mkdir(exist_ok=True)
    (C.ARTIFACTS / "evaluation.json").write_text(json.dumps(report, indent=2, default=float))
    (C.ROOT / "docs" / "EVALUATION.md").write_text(to_markdown(report))
    log(f"done in {report['runtime_s']}s -> artifacts/evaluation.json, docs/EVALUATION.md")
    return report


def _pct(x):
    return f"{100 * x:.1f}%"


def to_markdown(r: dict) -> str:
    L = ["# Evaluation", "",
         f"_Generated {r['generated_at']} by `python -m raktsetu evaluate`. All numbers come from simulation on a "
         "**synthetic** network (real locations, roads, weather and dengue years; generated demand and donations). "
         "They show the method works under stated assumptions, not a measured real-world outcome._", ""]

    L += ["## 1. Does the ML forecast beat simple baselines?", "",
          f"Held-out test period: {r['forecast']['test_period']}. Metric: WAPE (weighted absolute % error, lower is better). "
          "Per bank, per day.", "",
          "| Product, horizon | RaktSetu ML | 7-day average | Same weekday last week | Noise floor* |", "|---|---|---|---|---|"]
    nf = r["forecast"]["noise_floor"]
    for key, v in r["forecast"]["results"].items():
        prod = key.split("|")[0]
        L.append(f"| {key} | **{_pct(v['RaktSetu ML']['all'])}** | {_pct(v['MA7 (last 7 days)']['all'])} | "
                 f"{_pct(v['Same weekday last week']['all'])} | {_pct(nf[prod])} |")
    L += ["", "*Noise floor: error of the true expected demand. Daily requests at one bank are small, noisy counts, "
          "so even a perfect model has this much error. The ML model closes part of the gap between the baseline and that floor.", ""]

    fi = r["feature_importance"]["increase_in_wape_when_shuffled"]
    top = list(fi.items())[:6]
    L += ["**What drives the platelet forecast** (2024 dengue season; increase in WAPE when a feature is shuffled):", ""]
    L += [f"- `{k}`: +{100 * v:.1f} points" for k, v in top]
    L += [""]

    sr = r["surge_radar"]
    L += ["## 2. Surge radar: city-wide platelets 1-4 weeks ahead", "",
          f"Test period {sr['test_period']}. Target: {sr['target']}. Ramp-up = {sr['ramp_up_window']}.", "",
          "| Horizon | Surge radar (all / ramp-up) | Current level persists | Same week last year |", "|---|---|---|---|"]
    for k, v in sr["results"].items():
        L.append(f"| {k} | **{_pct(v['RaktSetu surge radar']['all'])}** / {_pct(v['RaktSetu surge radar']['ramp_up'])} | "
                 f"{_pct(v['Current level persists (MA7)']['all'])} / {_pct(v['Current level persists (MA7)']['ramp_up'])} | "
                 f"{_pct(v['Same week last year']['all'])} / {_pct(v['Same week last year']['ramp_up'])} |")
    L += ["", "For next week, simply assuming the current level persists is as good as the model. "
          "The radar earns its place 2-4 weeks out, which is the lead time needed to organise donor drives.", ""]

    seeds = sorted({x["seed"] for x in r["policy_runs"]})
    L += ["## 3. Policies: what changes for patients and for waste", "",
          f"Mean over {len(seeds)} random seeds (± standard deviation). Each seed regenerates demand and donations.", ""]
    for wn in WINDOWS:
        L += [f"### {wn}", "",
              "| Policy | Red-cell fill | Platelet fill | Red-cell wastage | Platelet wastage | Unmet units | Expired units | Trips | km |",
              "|---|---|---|---|---|---|---|---|---|"]
        for (pol, fc), lab in LABEL.items():
            s = r["policy_summary"].get(f"{wn}|{lab}")
            if not s:
                continue
            um = s["rbc_unmet"]["mean"] + s["plt_unmet"]["mean"]
            ex = s["rbc_expired"]["mean"] + s["plt_expired"]["mean"]
            tr = s["planned_trips"]["mean"] + s["emergency_trips"]["mean"]
            L.append(f"| {lab} | {_pct(s['rbc_fill_rate']['mean'])} ± {100 * s['rbc_fill_rate']['std']:.1f} | "
                     f"{_pct(s['plt_fill_rate']['mean'])} ± {100 * s['plt_fill_rate']['std']:.1f} | "
                     f"{_pct(s['rbc_wastage_rate']['mean'])} | {_pct(s['plt_wastage_rate']['mean'])} | {um:,.0f} | {ex:,.0f} | {tr:,.0f} | {s['total_km']['mean']:,.0f} |")
        base = r["policy_summary"][f"{wn}|{LABEL['reactive', None]}"]
        ours = r["policy_summary"][f"{wn}|{LABEL['raktsetu', 'ml']}"]
        du = 1 - (ours["rbc_unmet"]["mean"] + ours["plt_unmet"]["mean"]) / max(1, base["rbc_unmet"]["mean"] + base["plt_unmet"]["mean"])
        de = 1 - (ours["rbc_expired"]["mean"] + ours["plt_expired"]["mean"]) / max(1, base["rbc_expired"]["mean"] + base["plt_expired"]["mean"])
        L += ["", f"**vs today's phone-around: {100 * du:.0f}% fewer unmet requests and {100 * de:.0f}% fewer expired units**, "
              f"at the cost of {ours['total_km']['mean'] - base['total_km']['mean']:,.0f} more van-km.", ""]

    L += ["## 4. Sensitivity: does the conclusion survive different assumptions?", "",
          "2024 dengue season. Each row changes one assumption; the rest stay at their defaults.", "",
          "| Assumption | Value | Unmet (today → RaktSetu) | Expired (today → RaktSetu) |", "|---|---|---|---|"]
    sdf = pd.DataFrame(r["sensitivity_runs"])
    for (param, val), g in sdf.groupby(["param", "value"], sort=False):
        ru = (g.reactive_rbc_unmet + g.reactive_plt_unmet).mean()
        su = (g.raktsetu_rbc_unmet + g.raktsetu_plt_unmet).mean()
        re_ = (g.reactive_rbc_expired + g.reactive_plt_expired).mean()
        se = (g.raktsetu_rbc_expired + g.raktsetu_plt_expired).mean()
        L.append(f"| {g.label.iloc[0]} | {val} | {ru:,.0f} → {su:,.0f} ({100 * (su / max(ru, 1) - 1):+.0f}%) | "
                 f"{re_:,.0f} → {se:,.0f} ({100 * (se / max(re_, 1) - 1):+.0f}%) |")
    L += ["", "## 5. Reproducibility", "",
          "The optimiser uses 8 parallel CP-SAT workers with a 2% optimality gap, so two identical runs can pick "
          "different (equally good) plans. Same run twice:", ""]
    for k, (a, b) in r["reproducibility"].items():
        L.append(f"- `{k}`: {a} vs {b}")
    L += ["", f"_Evaluation runtime: {r['runtime_s']}s._", ""]
    return "\n".join(L)
