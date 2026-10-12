# RaktSetu (रक्त सेतु) — a bridge for blood

**RaktSetu forecasts blood and platelet requests at each of Jaipur's 18 blood banks and, every morning, tells the district coordinator which units to move where: before a patient is turned away, and before a unit expires on a shelf.**

Open source (MIT) · Python · OR-Tools · scikit-learn · FastAPI · React · Built for COMMIT FOR GOOD 2026

**Live demo:** https://abhishekjadli007-raktsetu.hf.space · [Hugging Face Space](https://huggingface.co/spaces/AbhishekJadli007/raktsetu)

---

## Documents

| Read this | For |
|---|---|
| [Project explainer](docs/PROJECT_EXPLAINER.md) ([PDF](docs/pdf/RaktSetu_Project_Explainer.pdf)) | What RaktSetu does and what it is trying to achieve, end to end, in plain language |
| [Solution brief](docs/SOLUTION_BRIEF.md) ([PDF](docs/pdf/RaktSetu_Solution_Brief.pdf)) | The 2-page submission summary |
| [Evaluation](docs/EVALUATION.md) | Every result, baseline, seed and sensitivity run |
| [Data and assumptions](data/ASSUMPTIONS.md) | What is real, what is generated, and why each number was chosen |
| [Architecture](docs/ARCHITECTURE.md) | Components, the optimisation model, the simulator |
| [Round 1 (A/B/C)](docs/ROUND1.md) · [Demo script](docs/DEMO_SCRIPT.md) | How the idea was refined; the demo walkthrough and likely judge questions |

## The problem

> **Blood-bank coordinators in Jaipur** cannot move stock to where it will be needed *before* it runs out or expires,
> **because** each bank plans alone and e-RaktKosh only shows today's stock,
> **which causes** platelet shortages in dengue season while red cells and platelets are discarded unused a few kilometres away.

- India **collected 14.6 million units in 2024–25, roughly its whole requirement**, so the gap is now distribution, not supply ([ORF, Oct 2025](https://www.orfonline.org/expert-speak/securing-india-s-lifeblood-for-a-reliable-national-blood-supply)).
- Yet **5–15% of collected units are wasted** (same source), and Indian blood banks **discarded about 28 lakh units between 2012 and 2016** (NACO data via RTI, [Business Insider 2017](https://www.businessinsider.in/india-lost-6-lakh-litres-of-blood-in-five-years/articleshow/58338754.cms)).
- In eight states including **Rajasthan, median stock is 0.6 units per 1,000 people, and 22% of banks rarely or never update e-RaktKosh** ([BMJ Global Health 2024](https://doaj.org/article/99ff305cac114d16a01b74de21e909c0), via ORF).
- **Platelets last 5 days.** In an October dengue surge, one Jaipur bank's platelet requests went from 15–20 a month to 50–60 a day ([LivLong](https://healthstory.livlong.com/news/increase-in-dengue-cases-leads-to-rising-demand-for-platelets)). Rajasthan recorded 12,514 dengue cases in 2024 and 20,749 in 2021 ([NCVBDC](https://ncvbdc.mohfw.gov.in/Doc/Dengue-Cases-deaths-2021-2026-till-April.pdf)).

**What exists and where it falls short.** e-RaktKosh gives visibility of current stock. It does not forecast, recommend transfers or warn of a surge. Today, a bank that runs out phones around. That is reactive, it happens after a patient is already waiting, and nobody moves near-expiry units proactively.

## What this does

| | |
|---|---|
| **Input** | A date (and optionally: the real stock at any bank, vans available, a crisis scenario) |
| **Output** | (1) Today's van trips (from bank → to bank, which blood groups, how many units) with the reasons for each; (2) shortages no van can fix, escalated to donor drives; (3) a 4-week platelet surge warning for the city |

Three parts, each compared against a simple baseline:

1. **Forecast:** a gradient-boosted model predicts each bank's red-cell and platelet requests 1–5 days ahead, using recent requests and *lagged real rainfall*. Rain leads dengue by ~8 weeks.
2. **Optimise:** an integer programme (OR-Tools CP-SAT) chooses the van trips that avert the most shortages and expiries, within the vans and cooler boxes available.
3. **Surge radar:** a city-wide model forecasts platelet need 1–4 weeks ahead so coordinators can book donors *before* the peak, because moving stock cannot fix a city-wide shortage.

## Example

```text
$ python -m raktsetu plan --date 2026-10-10
RaktSetu transfer plan for 2026-10-10
============================================================
8 trips moving 365 units today. 83 bank-product combinations are below their protected level;
133 units across the city are at risk of expiring unused.

1. SEVAYTAN -> SMS  (6.8 km, ~6 min)  23 x AB+, 14 x B+, 9 x O+, 2 x A-, 2 x B-
     - SMS holds 18 B+ red cells but expects ~66 requests in the next 5 days (protecting against up to 75).
     - SEVAYTAN has 14 B+ red cells likely to expire unused within 7 days, so moving them saves units that would otherwise be discarded.
     ...
Needs donors, not vans:
  ! Arrange 38 more platelets for BMCHRC (platelet donors or apheresis slots): no bank within reach can spare them ...
```

```text
$ python -m raktsetu simulate --start 2024-08-15 --end 2024-11-30      # the 2024 dengue season
policy       RBC fill   PLT fill  RBC waste  PLT waste      unmet    expired      trips         km
isolated        94.1%      76.6%      12.5%      14.2%      4,297      4,703          0          0
reactive        96.7%      84.7%      10.5%       5.0%      2,685      3,158        588      2,542
raktsetu        99.4%      86.4%       5.5%       3.1%      1,879      1,708        947      4,976
```

```text
$ python -m raktsetu radar --date 2024-08-20
Platelet surge radar for 2024-08-20  [ALERT]
  week of 2024-09-10: ~118.0/day  (80% band 89.9-166.8)
  Expected platelet need of ~118/day by the week of 2024-09-10 exceeds current production (~74/day). Schedule ~305 extra platelet units per week ...
```

Try it on an input we did not prepare: any date from 2016-07 to 2026-10, your own stock (`--set-stock SMS:PLT:0`), or a crisis
(`--separator-failure BMCHRC:2024-09-01:2024-09-30 --surge SMS:2024-09-20:120 --vans 1`).

## Results (simulation, 5 random seeds)

| 2024 dengue season | Red-cell fill | Platelet fill | Red-cell wastage | Platelet wastage | Unmet | Expired |
|---|---|---|---|---|---|---|
| Isolated banks | 94.0% | 77.3% | 12.4% | 14.1% | 4,218 | 4,718 |
| Phone-around (today) | 96.9% | 84.9% | 10.3% | 5.6% | 2,602 | 3,203 |
| **RaktSetu** | **99.8%** | **87.4%** | **4.8%** | **2.9%** | **1,664** | **1,538** |

**Compared with today's phone-around: 36% fewer unmet requests and 52% fewer expired units in the 2024 dengue season, and 80% fewer unmet and 43% fewer expired across 2025.** The cost is more driving (~2,650 extra van-km per season). The improvement holds across every assumption we varied, and **one van is enough** for Jaipur.

What the numbers also tell us, honestly:
- **Most of the gain comes from coordination**, not from the ML forecast. The ML model beats the 7-day average (WAPE 33.2% vs 35.8% for red cells, 52.8% vs 55.6% for platelets; noise floor 33.1% / 51.5%), but a perfect forecast would add only a little more.
- **At the dengue peak the whole city is short of platelets.** Sharing cannot create platelets. That is why the **surge radar** exists: at 3–4 weeks ahead its error is **13.6–14.6% vs 20.5–24.8%** for "current level persists". For next week, persistence is as good, and we say so.

Full tables, sensitivity analysis and reproducibility: [`docs/EVALUATION.md`](docs/EVALUATION.md).

## How it works

```mermaid
flowchart LR
  subgraph Real inputs
    OSM[OpenStreetMap<br/>18 blood banks] --> NET
    OSRM[OSRM<br/>road times] --> NET[Network]
    MET[Open-Meteo<br/>Jaipur weather] --> DEN
    NCV[NCVBDC<br/>dengue cases/yr] --> DEN[Dengue signal]
  end
  subgraph Generated, seeded
    DEN --> DEM[Requests per bank,<br/>group, day]
    NET --> DON[Donations, camps,<br/>replacement donors]
  end
  DEM --> SIM
  DON --> SIM[Day-by-day<br/>inventory simulator]
  MET --> FC[ML forecaster<br/>per bank, 1-5 days]
  MET --> SR[Surge radar<br/>city, 1-4 weeks]
  FC --> OPT[CP-SAT transfer<br/>optimiser]
  SIM <--> OPT
  OPT --> EXP[Explanations +<br/>escalations]
  SR --> EXP
  EXP --> API[FastAPI] --> UI[React control room]
  EXP --> CLI[CLI]
```

**Why these methods** (following "start from the problem"):
- *"What should we move today, given limited vans?"* is an allocation problem, so we use **optimisation** (CP-SAT integer programme; no training data needed).
- *"What happens over a season, or if a machine breaks?"* calls for **simulation**: a day-by-day inventory model with ageing, expiry, substitution and phone-around.
- *"How many requests tomorrow / in 4 weeks?"* is **forecasting**, always compared against a 7-day average and same-week-last-year baselines.
- *"Why should I trust this trip?"* is **explanation**: every trip lists its reasons, and impossible shortfalls are escalated rather than hidden.
- No LLM chat interface: removing it would change nothing. The system works without one.

Details and the optimisation model: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Data

**This project uses synthetically generated blood-bank demand on a real network.**
Real inputs: blood-bank locations (OpenStreetMap, ODbL), road travel times (OSRM on OSM, ODbL), Jaipur daily weather 2016–2026 (Open-Meteo / ERA5, CC BY 4.0), Rajasthan annual dengue cases (NCVBDC / Parliament answers), the Indian blood-group distribution (Agrawal et al. 2014).
Generated inputs: daily requests and donations per bank and blood group, camps, bank profiles.
Generation script: [`data/generate.py`](data/generate.py) (seed 42). Every parameter, value and justification: [`data/ASSUMPTIONS.md`](data/ASSUMPTIONS.md).
Imputed values (dengue counts for 2018–2020 and 2026) are flagged in `data/generated/drivers.csv`.
**Limitation:** results demonstrate the method and are not a measured real-world outcome.

## Installation

```bash
git clone https://github.com/AbhishekJadli007/raktsetu.git && cd raktsetu
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Trained models (`artifacts/*.joblib`) and the real-data cache (`data/raw/`) are committed, so everything runs offline.
To rebuild from scratch: `python -m raktsetu fetch && python -m raktsetu train && python -m raktsetu evaluate`.

**Web app** (needs Node 20+):

```bash
cd web && npm install && npm run build && cd ..
uvicorn api.main:app --port 8000          # open http://localhost:8000
```

For frontend development, run `npm run dev` in `web/` (it proxies `/api` to port 8000).
**Docker:** `docker build -t raktsetu . && docker run -p 8000:8000 raktsetu`.
**Deploy (free):** `python deploy/huggingface.py` uploads to a free Hugging Face Space (see [`deploy/README.md`](deploy/README.md)).

## Usage

| Command | What it does |
|---|---|
| `python -m raktsetu plan --date 2026-10-10` | Today's transfers with reasons (`--json` for machine output) |
| `python -m raktsetu plan --date 2024-09-20 --set-stock SMS:PLT:0 --set-stock FORTIS:O-:2` | Re-plan around stock you type in |
| `python -m raktsetu radar --date 2024-08-20` | 4-week platelet surge warning |
| `python -m raktsetu simulate --start 2024-08-15 --end 2024-11-30 [scenario flags]` | Compare isolated / phone-around / RaktSetu |
| `python -m raktsetu evaluate [--quick]` | Regenerate `docs/EVALUATION.md` (~8 min; `--quick` ~2 min) |
| `python -m raktsetu train` | Retrain forecaster and surge radar |
| `python -m raktsetu precompute [--fresh]` | Save the web demo flows to `artifacts/cache/` so small servers answer them instantly (`--fresh` after engine changes) |
| `pytest` | 15 tests: reproducibility, conservation of units, solver limits, API |

Scenario flags: `--dengue-scale 1.7`, `--kappa 4`, `--donation-change -0.3`, `--separator-failure BANK:START:END`, `--collection-halt BANK:START:END`, `--surge BANK:DATE:UNITS`, `--vans 1`, `--seed 7`.

API docs (Swagger) at `http://localhost:8000/docs`.

## Evaluation

What we measured, against what baseline, and the result: [`docs/EVALUATION.md`](docs/EVALUATION.md) (generated by `python -m raktsetu evaluate`).

- Forecasts: time split (train 2016–2022, validate 2023, test 2024–2025), WAPE vs 7-day average and same-weekday-last-week, plus the noise floor.
- Policies: 5 seeds × 2 windows (2024 dengue season; 2025 full year) × 5 policies, including a perfect-forecast upper bound.
- Sensitivity: dengue peak size, collection/demand ratio, vans, service level.
- Reproducibility: the same run twice (parallel solver), differences under 1%.

## Limitations

- **Synthetic demand.** Per-bank daily data is not public. Bank profiles are our guesses. A pilot needs real e-RaktKosh stock feeds.
- **The dengue signal is modelled** from real rainfall and real annual counts using published lags, not fitted to weekly district case data.
- **Clinical and legal simplifications:** platelets pooled across groups; inter-bank transfer rules (licensing, cross-match, cold chain) must be confirmed with the Rajasthan State Blood Transfusion Council.
- **"Unmet request" is an indicator,** not a count of harmed patients. In reality patients wait, are referred, or families donate.
- **The surge radar is a warning, not a count.** Its error during the ramp-up is ~17–24%.
- **More driving.** RaktSetu roughly doubles van-km versus phone-around, which we report as a cost.
- **Parallel solver:** two identical runs can choose different but equally good plans (<1% difference).

The strongest objection we could not fully answer: *"Banks are run by different owners (government, NGO, private). Why would they share?"*
Our answer: the plan only moves stock a bank can spare above its own protected need, and in dengue season every bank is sometimes on the receiving end. But adoption needs a state-level mandate or incentive, which is a policy question, not a software one.

## Project structure

```
raktsetu/        engine: world.py (data) · forecast.py · surge.py · optimizer.py · simulator.py · explain.py · evaluate.py · __main__.py (CLI)
api/main.py      FastAPI backend (also serves the built web app)
web/             React + Vite + Tailwind + Leaflet + Recharts frontend
data/            fetch_real_data.py · generate.py · ASSUMPTIONS.md · bank_profiles.csv · raw/ (real, cached) · sample/
artifacts/       trained models + evaluation.json
docs/            ARCHITECTURE.md · EVALUATION.md
tests/           pytest suite
```

## Author

Built solo by **Abhishek Jadli** ([@AbhishekJadli007](https://github.com/AbhishekJadli007)) for COMMIT FOR GOOD 2026: problem research, data pipeline, forecasting, optimisation, simulation, API, web app and documentation.

## Licence

MIT. See [LICENSE](LICENSE). Third-party data keeps its own licence. See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

*RaktSetu is a research prototype and decision-support tool. It is not a medical device, and every transfer must be approved by a qualified blood-bank officer.*
