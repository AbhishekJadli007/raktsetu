"""RaktSetu HTTP API (FastAPI). Thin layer over raktsetu.engine; also serves the built web app.

    uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import hashlib
import json
import threading
from contextlib import asynccontextmanager
from functools import lru_cache, wraps

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from raktsetu import config as C
from raktsetu import surge
from raktsetu.engine import compare_policies, forecaster, todays_plan
from raktsetu.forecast import MA7, product_demand
from raktsetu.world import Scenario, build_world

HEAVY = threading.Lock()  # the optimiser already uses every core; run one heavy job at a time

# Precomputed results for the demo flows (written by `python -m raktsetu precompute`), so a small free
# server answers them instantly. Anything else is computed live. Re-run precompute after changing the engine.
CACHE_DIR = C.ARTIFACTS / "cache"
WRITE_CACHE = False


def disk_cache(kind: str):
    def deco(fn):
        @wraps(fn)
        def wrapper(key: str):
            path = CACHE_DIR / f"{kind}-{hashlib.sha1(key.encode()).hexdigest()[:16]}.json"
            if path.exists():
                return json.loads(path.read_text())
            out = fn(key)
            if WRITE_CACHE:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(out, separators=(",", ":")))
            return out
        return wrapper
    return deco


def _warm():
    try:
        with HEAVY:
            _plan_cached(json.dumps(PlanIn().model_dump(), sort_keys=True))
            _sim_cached(json.dumps(SimIn().model_dump(), sort_keys=True))
    except Exception as e:  # warming is best-effort
        print("warm-up failed:", e)


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm, daemon=True).start()  # precompute the default plan and simulation
    yield


app = FastAPI(title="RaktSetu API", version="1.0.0", lifespan=lifespan,
              description="Predictive blood sharing between Jaipur's blood banks. All data is simulated on real structure.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
WEB = C.ROOT / "web" / "dist"
MAX_SIM_DAYS = 200


# ------------------------------------------------------------------ models
class BankWindow(BaseModel):
    bank: str
    start: str
    end: str


class SurgeEvent(BaseModel):
    bank: str
    date: str
    units: int = Field(60, ge=1, le=500)


class ScenarioIn(BaseModel):
    seed: int = C.SEED
    dengue_scale: float = Field(1.0, ge=0, le=5)
    kappa: float = Field(C.DENGUE_PLT_KAPPA, ge=0, le=10)
    donation_change: float = Field(0.0, ge=-0.9, le=1.0)
    change_start: str | None = None
    change_end: str | None = None
    separator_failure: list[BankWindow] = []
    collection_halt: list[BankWindow] = []
    surge: list[SurgeEvent] = []
    vans: int = Field(C.VANS, ge=0, le=6)

    def to_scenario(self) -> Scenario:
        return Scenario(
            seed=self.seed, dengue_scale=self.dengue_scale, kappa=self.kappa, donation_change=self.donation_change,
            change_start=self.change_start, change_end=self.change_end,
            separator_failure=tuple((x.bank, x.start, x.end) for x in self.separator_failure),
            collection_halt=tuple((x.bank, x.start, x.end) for x in self.collection_halt),
            surge=tuple((x.bank, x.date, x.units) for x in self.surge), vans=self.vans,
        )


class PlanIn(BaseModel):
    date: str = "2026-10-10"
    history: str = "isolated"
    scenario: ScenarioIn = ScenarioIn()
    overrides: dict[str, dict[str, int]] | None = None


class SimIn(BaseModel):
    start: str = "2024-08-15"
    end: str = "2024-11-30"
    scenario: ScenarioIn = ScenarioIn()
    forecaster: str = "ml"


# ------------------------------------------------------------------ helpers
def _check_date(w, d: str, lo_pad: int = 130):
    ts = pd.Timestamp(d)
    if ts < w.dates[lo_pad] or ts > w.dates[-1]:
        raise HTTPException(400, f"date must be between {w.dates[lo_pad].date()} and {w.dates[-1].date()}")


def _guard(fn):
    try:
        return fn()
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ------------------------------------------------------------------ endpoints
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    w = build_world()
    b = w.banks
    return {
        "banks": [{"short": r.short, "name": r.name, "lat": r.lat, "lon": r.lon, "operator": r.operator_type,
                   "role": r.role, "runs_camps": bool(r.runs_camps)} for r in b.itertuples()],
        "dates": {"first": str(w.dates[130].date()), "last": str(w.dates[-1].date()), "today": str(w.dates[-1].date())},
        "skus": C.SKUS,
        "defaults": {"vans": C.VANS, "kappa": C.DENGUE_PLT_KAPPA, "quantile": C.SERVICE_QUANTILE,
                     "trips_per_van": C.TRIPS_PER_VAN, "box_capacity": C.BOX_CAPACITY},
        "dengue_cases_rajasthan": C.RAJASTHAN_DENGUE_CASES,
    }


@app.get("/api/plan")
def plan_get(date: str = "2026-10-10", history: str = "isolated", vans: int = C.VANS):
    return plan_post(PlanIn(date=date, history=history, scenario=ScenarioIn(vans=vans)))


@app.post("/api/plan")
def plan_post(body: PlanIn):
    sc = body.scenario.to_scenario()
    w = build_world(sc)
    _check_date(w, body.date)
    if body.history not in ("isolated", "reactive", "raktsetu"):
        raise HTTPException(400, "history must be isolated, reactive or raktsetu")
    key = json.dumps(body.model_dump(), sort_keys=True)
    with HEAVY:
        return _guard(lambda: _plan_cached(key))


@lru_cache(maxsize=64)
@disk_cache("plan")
def _plan_cached(key: str):
    b = PlanIn(**json.loads(key))
    return todays_plan(b.date, b.scenario.to_scenario(), b.history, b.overrides)


@app.get("/api/radar")
def radar(date: str = "2026-10-10"):
    w = build_world()
    _check_date(w, date)
    return surge.radar(w, date)


@app.post("/api/simulate")
def simulate_post(body: SimIn):
    sc = body.scenario.to_scenario()
    w = _guard(lambda: build_world(sc))
    _check_date(w, body.start)
    _check_date(w, body.end)
    n = (pd.Timestamp(body.end) - pd.Timestamp(body.start)).days + 1
    if not 7 <= n <= MAX_SIM_DAYS:
        raise HTTPException(400, f"simulate between 7 and {MAX_SIM_DAYS} days")
    key = json.dumps(body.model_dump(), sort_keys=True)
    with HEAVY:
        return _guard(lambda: _sim_cached(key))


@lru_cache(maxsize=32)
@disk_cache("sim")
def _sim_cached(key: str):
    b = SimIn(**json.loads(key))
    out = compare_policies(b.start, b.end, b.scenario.to_scenario(), b.forecaster, keep=True)
    w, res = out["world"], out["results"]
    first = next(iter(res.values()))
    payload = {"start": b.start, "end": b.end, "dates": [str(d.date()) for d in first.dates],
               "banks": list(w.banks.short), "policies": {},
               # mean daily requests per bank over the window: [red cells, platelets] (to colour days of cover)
               "bank_mean_demand": np.stack([first.demand[:, :, :8].sum(-1).mean(0), first.demand[:, :, 8].mean(0)], -1).round(2).tolist()}
    for p, r in res.items():
        tr = pd.DataFrame(r.transfers) if r.transfers else pd.DataFrame(columns=["day", "src", "dst", "sku", "units", "kind"])
        per_day = [[] for _ in r.dates]
        if len(tr):
            g = tr.groupby(["day", "src", "dst", "kind"]).units.sum().reset_index()
            for row in g.itertuples():
                per_day[int(row.day)].append([int(row.src), int(row.dst), int(row.units), row.kind])
        payload["policies"][p] = {
            "kpis": r.kpis(w.banks, w.drive_km),
            "daily": {
                "unmet_rbc": r.unmet[:, :, :8].sum(axis=(1, 2)).astype(int).tolist(),
                "unmet_plt": r.unmet[:, :, 8].sum(axis=1).astype(int).tolist(),
                "expired_rbc": r.expired[:, :, :8].sum(axis=(1, 2)).astype(int).tolist(),
                "expired_plt": r.expired[:, :, 8].sum(axis=1).astype(int).tolist(),
                "demand_plt": r.demand[:, :, 8].sum(axis=1).astype(int).tolist(),
                "demand_rbc": r.demand[:, :, :8].sum(axis=(1, 2)).astype(int).tolist(),
            },
            # per day, per bank: [red-cell stock, platelet stock, unmet that day]
            "bank_days": np.stack([r.stock[:, :, :8].sum(-1), r.stock[:, :, 8], r.unmet.sum(-1)], -1).astype(int).tolist(),
            "transfers": per_day,
        }
    return payload


@app.get("/api/forecast")
def forecast_series(bank: str = "SMS", product: str = "PLT", start: str = "2024-07-01", end: str = "2024-12-15"):
    w = build_world()
    _check_date(w, start)
    _check_date(w, end)
    b = _guard(lambda: w.bank_index(bank))
    p = {"RBC": 0, "PLT": 1}.get(product.upper())
    if p is None:
        raise HTTPException(400, "product must be RBC or PLT")
    t0, t1 = w.idx(start), w.idx(end) + 1
    D = product_demand(w)
    ml = forecaster("ml").window(w, t0, t1)[:, b, p, 0]
    ma = MA7().window(w, t0, t1)[:, b, p, 0]
    return {"bank": w.banks.short[b], "product": product.upper(), "dates": [str(d.date()) for d in w.dates[t0:t1]],
            "actual": D[t0:t1, b, p].astype(int).tolist(), "ml": np.round(ml, 2).tolist(), "ma7": np.round(ma, 2).tolist(),
            "true_mean": np.round(w.mu_true[t0:t1, b, p], 2).tolist()}


@app.get("/api/drivers")
def drivers(start: str = "2024-01-01", end: str = "2024-12-31"):
    """City-level view: real rainfall, the dengue signal it drives, platelet requests and production."""
    w = build_world()
    t0, t1 = w.idx(start), w.idx(end) + 1
    wx = w.weather.reindex(w.dates[t0:t1])
    return {"dates": [str(d.date()) for d in w.dates[t0:t1]],
            "rain_mm": wx.rain_mm.round(1).fillna(0).tolist(), "temp_c": wx.temp_mean_c.round(1).tolist(),
            "dengue_signal": np.round(w.dengue_shape[t0:t1] * w.dengue_amp[t0:t1], 3).tolist(),
            "plt_requests": w.demand[t0:t1, :, C.PLT].sum(1).astype(int).tolist(),
            "plt_produced": w.collections[t0:t1, :, C.PLT].sum(1).astype(int).tolist(),
            "rbc_requests": w.demand[t0:t1, :, :8].sum((1, 2)).astype(int).tolist()}


@app.get("/api/evaluation")
def evaluation():
    p = C.ARTIFACTS / "evaluation.json"
    if not p.exists():
        raise HTTPException(404, "Run `python -m raktsetu evaluate` first")
    d = json.loads(p.read_text())
    d.pop("policy_runs", None)
    return d


# ------------------------------------------------------------------ web app
if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = WEB / path
        return FileResponse(f if path and f.is_file() else WEB / "index.html")


# ------------------------------------------------------------------ precompute (demo flows)
# These mirror exactly what the web app sends (see web/src/views/SimLab.tsx PRESETS and ControlRoom.tsx).
_SEP = BankWindow(bank="BMCHRC", start="2024-09-01", end="2024-10-15")
_SURGE = SurgeEvent(bank="SMS", date="2024-09-20", units=120)
DEMO_SIMS = [
    SimIn(scenario=ScenarioIn()),
    SimIn(scenario=ScenarioIn(dengue_scale=1.7)),
    SimIn(scenario=ScenarioIn(separator_failure=[_SEP])),
    SimIn(scenario=ScenarioIn(surge=[_SURGE])),
    SimIn(start="2025-04-01", end="2025-07-31", scenario=ScenarioIn(donation_change=-0.35)),
    SimIn(scenario=ScenarioIn(dengue_scale=1.7, vans=1, separator_failure=[_SEP], surge=[_SURGE])),
]


def demo_plans(today: str) -> list[PlanIn]:
    plans = [PlanIn(date=today, scenario=ScenarioIn(vans=v)) for v in (1, 2, 3)]
    plans += [PlanIn(date=today, history="reactive"), PlanIn(date="2024-09-20"), PlanIn(date="2024-08-20")]
    plans += [PlanIn(date=today, overrides={"SMS": {"PLT": 0}}), PlanIn(date=today, overrides={"BMCHRC": {"PLT": 0}})]
    return plans


def precompute(fresh: bool = False, log=print):
    """Compute and save the demo flows to artifacts/cache/ (commit them for deployment).

    Existing results are kept unless fresh=True (use that after changing the engine).
    """
    global WRITE_CACHE
    import shutil
    import time
    if fresh:
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
    WRITE_CACHE = True
    t0 = time.time()
    today = str(build_world().dates[-1].date())
    for b in demo_plans(today):
        _plan_cached(json.dumps(b.model_dump(), sort_keys=True))
        log(f"  plan {b.date} history={b.history} vans={b.scenario.vans} overrides={b.overrides}  ({time.time() - t0:.0f}s)")
    for b in DEMO_SIMS:
        _sim_cached(json.dumps(b.model_dump(), sort_keys=True))
        log(f"  simulate {b.start}..{b.end} {b.scenario.model_dump(exclude_defaults=True)}  ({time.time() - t0:.0f}s)")
    WRITE_CACHE = False
    n = len(list(CACHE_DIR.glob("*.json")))
    log(f"saved {n} results to {CACHE_DIR.relative_to(C.ROOT)}/ in {time.time() - t0:.0f}s")
