# Data and assumptions

RaktSetu runs on a **hybrid** dataset: the network, roads, weather and the size of each dengue year are real.
The daily requests and donations at each bank are **generated**, because per-bank daily blood-bank data is not public in India.

> **What this means for every result in this repository:** the simulation shows that the method works under these assumptions.
> It is **not** a measured real-world outcome. The correct claim is: *"On a simulated Jaipur network with these assumptions,
> RaktSetu reduced unmet requests by X% compared with phone-around sharing, which suggests it is worth piloting with real stock data."*

Regenerate everything with:

```bash
python data/fetch_real_data.py   # optional: re-download the real inputs (cached copies are committed)
python data/generate.py          # writes data/generated/ and data/sample/ (seed 42)
```

## Real inputs

| File | What | Source | Licence |
|---|---|---|---|
| `raw/blood_banks_jaipur_osm.csv` | 18 blood banks in Jaipur: name, coordinates, operator type | OpenStreetMap via Overpass API (query in `raw/SOURCES.json`) | ODbL 1.0 |
| `raw/travel_matrix_osrm.csv` | Driving time and distance between every pair of banks (324 pairs) | OSRM demo server on OpenStreetMap roads | ODbL 1.0 |
| `raw/weather_jaipur_openmeteo.csv` | Daily rain, mean/max temperature, humidity, 2016-01-01 to 2026-10-10 | Open-Meteo historical API (ERA5 reanalysis) | CC BY 4.0 |
| `raktsetu/config.py: RAJASTHAN_DENGUE_CASES` | Rajasthan dengue cases: 2015 4,043 · 2016 5,292 · 2017 8,387 · 2021 20,749 · 2022 13,491 · 2023 13,924 · 2024 12,514 · 2025 4,348 | [NCVBDC](https://ncvbdc.mohfw.gov.in/Doc/Dengue-Cases-deaths-2021-2026-till-April.pdf) (2021–25); [Rajya Sabha answer](https://rsdebate.nic.in/bitstream/123456789/680515/2/PQ_244_02012018_U1727_p313_p316.pdf) (2015–17) | Government of India public data |
| `config.py: ABO_SHARE, RH_POS` | O 37.12%, B 32.26%, A 22.88%, AB 7.74%; Rh+ 94.61% | [Agrawal et al. 2014, Asian J Transfus Sci 8(2):121–125](https://pmc.ncbi.nlm.nih.gov/articles/PMC4140055), 10,000 donors | CC BY-NC-SA (article) |

**Imputed values (flagged):** we could not retrieve Rajasthan's dengue counts for 2018, 2019, 2020 or the full 2026 season.
These years use the median of the real years. `generated/drivers.csv` marks them with `dengue_amplitude_imputed = True`.
None of the test years (2024, 2025) is imputed.

## Generated inputs and every assumption

Values marked **[SOURCE]** come from a cited document. Values marked **[GUESS]** are ours. The sensitivity analysis
(`docs/EVALUATION.md`, section 4) varies the guesses that matter most.

### Scale

| Parameter | Value | Basis |
|---|---|---|
| Network red-cell requests | 190 units/day | **[GUESS, order of magnitude]** India needs ~14.6M units/yr ([ORF 2025](https://www.orfonline.org/expert-speak/securing-india-s-lifeblood-for-a-reliable-national-blood-supply)) for ~1.4B people ≈ 10.4 per 1,000/yr. Jaipur district ~6.6M (Census 2011) → ~190/day. Jaipur is a referral hub, so real demand is likely higher. |
| Baseline platelet requests | 45 units/day | **[GUESS]** outside dengue season |
| Collection / demand | 1.08 | **[SOURCE-ish]** national collection (14.6M) ≈ requirement (ORF 2025); we allow 8% surplus. Varied 0.98–1.18 in sensitivity. |
| Replacement donors | 30% of supply, given at the treating bank about a day after a request | **[SOURCE]** ~30% replacement / ~70% voluntary (ORF 2025) |
| Bank collection share | 50% from the bank's profile, 50% from its own demand | **[GUESS]** banks partly plan drives around their own use |
| Daily request noise | Negative binomial, k = 12 (red cells), 6 (platelets) | **[GUESS]** overdispersed counts |
| Day of week | Mon 1.06 … Sun 0.84 | **[GUESS]** fewer elective surgeries on Sunday |
| Blood-group mix per bank | Population mix + small Dirichlet variation (concentration 600) | **[GUESS]** |

### Banks (`data/bank_profiles.csv`)

Each bank's share of red-cell requests, platelet requests and collection, its platelet yield, and whether it runs camps.
These are **[GUESS]**es from the hospital type in the bank's name: a cancer hospital uses many platelets, a thalassaemia
centre uses many red cells, maternity hospitals use red cells, and camp-running NGO banks collect more than they issue.
The `basis` column explains each row. **This is the first thing a pilot should replace with real numbers.**

### Dengue

| Parameter | Value | Basis |
|---|---|---|
| Rain → dengue lag | Gaussian kernel centred at 56 days (sd 21) | **[SOURCE]** pan-India weekly study: rainfall risk peaks at 8–15-week lags ([Epidemiol Infect 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6518529/)); Delhi and Bhopal studies report ~2-month lags |
| Temperature suitability | Gaussian around 29 °C (sd 4.5) over the last 21 days | **[SOURCE]** same study: risk highest near 30 °C at 0–3-week lags |
| Season shape | Normalised to peak 1 within each year, raised to the power 1.5 | **[GUESS]** |
| Season severity | Real annual Rajasthan cases ÷ median of real years | **[SOURCE]** NCVBDC |
| Peak platelet multiplier in a median year | 1 + κ = 3.5× baseline (κ = 2.5) | **[GUESS]**, deliberately conservative: a Jaipur bank reported 15–20/month → 50–60/day ([LivLong](https://healthstory.livlong.com/news/increase-in-dengue-cases-leads-to-rising-demand-for-platelets)). Varied κ = 1.5–4 in sensitivity. |
| Red-cell spill-over | +8% at peak | **[GUESS]** |
| Donor response in season | Walk-ins +25% × season; platelet yield × (1 + 1.2 × season), capped at 75% | **[GUESS]** families and drives respond to dengue |

### Donations

| Parameter | Value | Basis |
|---|---|---|
| Summer dip (May–June) | −22% walk-ins | **[GUESS]** heat, colleges closed |
| Winter bump (Dec–Feb) | +5% walk-ins; camp rate × 1.5 | **[GUESS]** |
| Camps | 3.5% chance per day at camp-running banks, 40–120 units | **[GUESS]** |
| Fixed camp days | 1 October, 14 June | **[SOURCE]** National Voluntary Blood Donation Day and World Blood Donor Day |
| Processing | Collected today, issuable tomorrow | **[GUESS]** testing and separation take about a day |

### Clinical and logistics

| Parameter | Value | Basis |
|---|---|---|
| Shelf life | Red cells 35 days (CPDA-1), platelets 5 days | **[SOURCE]** standard storage limits |
| Red-cell substitution | ABO/Rh compatible, exact group first, O− last | **[SOURCE]** standard compatibility |
| Platelets | Pooled across blood groups | **[GUESS / simplification]** |
| Issuing | Oldest unit first (FEFO) | Standard practice |
| Vans | 2, 4 trips each, 50 units per box | **[GUESS]** results barely change with 1–3 vans (sensitivity) |
| Max drive | 60 minutes | **[GUESS]** cold-chain safety |
| Phone-around baseline | Calls the 3 nearest banks; each lends only stock above 3 days of its own use | **[GUESS]** what banks do today |
| Protected demand | 80th percentile over 5 days (red cells) or 3 days (platelets) | **[GUESS]** varied 0.7–0.9 in sensitivity |
| Optimiser weights | Platelet unit 3, Rh− unit 2, Rh+ unit 1, expiry saved 1, trip 1.5 + 0.08/min | **[GUESS]** |

## What this data cannot show

- Whether real Jaipur banks hold the stock imbalances we simulate. That needs real stock data (e-RaktKosh).
- The true size of the dengue platelet surge at each bank.
- Clinical outcomes. "Unmet requests" is an indicator of harm, not a count of patients harmed.
- Legal and regulatory feasibility of routine inter-bank transfers, which must be confirmed with the State Blood Transfusion Council.

## Validation checks we ran

- **Sanity:** demand non-negative; collection ≈ 1.08 × demand; Sep–Oct platelet demand > 1.5× Jan–Mar (`tests/test_world.py`).
- **Comparison with real figures:** the phone-around baseline produces 10–12% red-cell wastage, inside the 5–15% range reported nationally (ORF 2025).
- **Sensitivity:** see `docs/EVALUATION.md` section 4. The improvement holds across every value tested.
