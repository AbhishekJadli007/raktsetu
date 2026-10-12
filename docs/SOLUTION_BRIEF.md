# RaktSetu — Solution brief

*Predictive blood and platelet sharing between Jaipur's blood banks · COMMIT FOR GOOD 2026 · MIT licence*

## 1. Problem

**Blood-bank coordinators in Jaipur cannot move stock to where it will be needed before it runs out or expires, because each bank plans alone and e-RaktKosh only shows today's stock, which causes platelet shortages in dengue season while units are discarded unused a few kilometres away.**

**Who is affected.** Patients who need red cells (surgery, trauma, obstetric haemorrhage, thalassaemia) and platelets (dengue, chemotherapy). Their families, who are sent from bank to bank. Blood-bank officers. Donors whose blood expires unused.

**Evidence.**
- National collection reached 14.6 million units in 2024–25, roughly the requirement, so the problem is distribution, not supply (ORF, 2025).
- 5–15% of collected units are wasted (ORF, 2025). About 28 lakh units were discarded between 2012 and 2016 (NACO via RTI).
- In eight states including Rajasthan, median stock is 0.6 units per 1,000 people and 22% of banks rarely update e-RaktKosh (BMJ Global Health, 2024).
- Platelets last 5 days. Rajasthan had 12,514 dengue cases in 2024 and 20,749 in 2021 (NCVBDC). One Jaipur bank's platelet requests went from 15–20 a month to 50–60 a day in an October surge.

**What exists, and the gap.** e-RaktKosh provides visibility. Phone-around sharing happens after a patient is already waiting, and nobody moves near-expiry units proactively. Nothing forecasts, recommends or warns.

## 2. Approach

Input: a date (plus, optionally, real stock typed in, vans available, or a crisis scenario).
Output: today's van trips with reasons, shortfalls escalated to donor drives, and a 4-week platelet surge warning.

| Question | Method | Baseline it must beat |
|---|---|---|
| How many requests at each bank, 1–5 days ahead? | Gradient boosting (Poisson), features: recent requests + lagged real rainfall | 7-day average; same weekday last week |
| What should move today, given limited vans? | Integer programme (OR-Tools CP-SAT): maximise shortages + expiries averted − travel; vans, cooler boxes, each bank's own protected need | Phone-around after a stock-out |
| Will the city run short of platelets in 2–4 weeks? | City-level gradient boosting on rainfall lagged 4–12 weeks | Current level persists; same week last year |
| What happens in a crisis? | Day-by-day inventory simulator: ageing, expiry, ABO/Rh substitution, phone-around | — |

**Data.** Real: 18 blood banks (OpenStreetMap), road times (OSRM), Jaipur weather 2016–2026 (Open-Meteo), Rajasthan dengue cases (NCVBDC), blood-group mix (10,000-donor study). Generated (seeded, every assumption listed): daily requests and donations per bank. Results validate the method, not a real-world outcome.

## 3. Results (simulation, 5 seeds)

| | 2024 dengue season | 2025 full year |
|---|---|---|
| Unmet requests vs phone-around | **−36%** | **−80%** |
| Expired units vs phone-around | **−52%** | **−43%** |
| Red-cell fill rate | 96.9% → **99.8%** | 93.9% → **99.8%** |
| Red-cell wastage | 10.3% → **4.8%** | 11.6% → **5.5%** |
| Cost | +2,650 van-km | +11,300 van-km |

- **Sensitivity:** the improvement holds for every assumption varied (dengue peak 1.5–4×, collection 0.98–1.18× demand, 1–3 vans, service level 0.7–0.9). **One van is enough** for Jaipur.
- **Forecasting:** the ML model beats the 7-day average (WAPE 33.2% vs 35.8% red cells; 52.8% vs 55.6% platelets; noise floor 33.1% / 51.5%). Most of the gain comes from coordination, not the forecast.
- **Surge radar:** 3–4 weeks ahead, error 13.6–14.6% vs 20.5–24.8% for persistence. For next week, persistence is as good.

## 4. What we learned, and what is next

1. **Coordination beats prediction.** A simple forecast plus an optimiser captures most of the value. That makes the system cheap to deploy.
2. **At the dengue peak the city is genuinely short of platelets.** No reallocation fixes that, so the 2–4-week surge radar, which triggers donor drives, is the right second lever.
3. **Pilot plan:** one district, read-only e-RaktKosh stock export, plan reviewed by the District Blood Transfusion Officer each morning for 8 weeks of dengue season, then compare discards and turn-aways against the previous season.

**Limitations:** synthetic demand; bank profiles guessed; platelets pooled across groups; inter-bank transfer rules to be confirmed with the Rajasthan State Blood Transfusion Council; more driving.

**Repository:** README with install and run steps, `data/ASSUMPTIONS.md`, `docs/ARCHITECTURE.md`, `docs/EVALUATION.md`, 15 tests, Dockerfile, CONTRIBUTING, MIT licence.
