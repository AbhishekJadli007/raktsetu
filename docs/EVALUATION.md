# Evaluation

_Generated 2026-10-12T16:24:13 by `python -m raktsetu evaluate`. All numbers come from simulation on a **synthetic** network (real locations, roads, weather and dengue years; generated demand and donations). They show the method works under stated assumptions, not a measured real-world outcome._

## 1. Does the ML forecast beat simple baselines?

Held-out test period: 2024-01-01 to 2025-12-26. Metric: WAPE (weighted absolute % error, lower is better). Per bank, per day.

| Product, horizon | RaktSetu ML | 7-day average | Same weekday last week | Noise floor* |
|---|---|---|---|---|
| RBC|h+0 | **33.2%** | 35.8% | 46.5% | 33.1% |
| RBC|h+1 | **33.1%** | 35.8% | 46.5% | 33.1% |
| RBC|h+2 | **33.2%** | 35.7% | 46.5% | 33.1% |
| RBC|h+3 | **33.2%** | 35.9% | 46.5% | 33.1% |
| RBC|h+4 | **33.2%** | 35.7% | 46.5% | 33.1% |
| PLT|h+0 | **52.8%** | 55.6% | 71.7% | 51.5% |
| PLT|h+1 | **52.7%** | 55.6% | 71.7% | 51.5% |
| PLT|h+2 | **52.7%** | 55.7% | 71.7% | 51.5% |

*Noise floor: error of the true expected demand. Daily requests at one bank are small, noisy counts, so even a perfect model has this much error. The ML model closes part of the gap between the baseline and that floor.

**What drives the platelet forecast** (2024 dengue season; increase in WAPE when a feature is shuffled):

- `ma28`: +34.5 points
- `city_trend`: +4.4 points
- `ma7`: +2.2 points
- `bank`: +0.8 points
- `dow`: +0.6 points
- `ma7_prev`: +0.2 points

## 2. Surge radar: city-wide platelets 1-4 weeks ahead

Test period 2024-01-01 to 2025-12-31. Target: mean daily city-wide platelet requests in week k ahead. Ramp-up = forecasts issued 15 Jul - 30 Sep (as the dengue surge builds).

| Horizon | Surge radar (all / ramp-up) | Current level persists | Same week last year |
|---|---|---|---|
| week+1 | **10.8%** / 13.8% | 10.2% / 10.6% | 34.0% / 49.9% |
| week+2 | **11.9%** / 16.5% | 15.3% / 17.2% | 34.0% / 52.7% |
| week+3 | **13.6%** / 21.4% | 20.5% / 23.1% | 33.9% / 56.2% |
| week+4 | **14.6%** / 23.7% | 24.8% / 27.1% | 33.9% / 57.1% |

For next week, simply assuming the current level persists is as good as the model. The radar earns its place 2-4 weeks out, which is the lead time needed to organise donor drives.

## 3. Policies: what changes for patients and for waste

Mean over 5 random seeds (± standard deviation). Each seed regenerates demand and donations.

### 2024 dengue season

| Policy | Red-cell fill | Platelet fill | Red-cell wastage | Platelet wastage | Unmet units | Expired units | Trips | km |
|---|---|---|---|---|---|---|---|---|
| Isolated banks | 94.0% ± 0.9 | 77.3% ± 1.4 | 12.4% | 14.1% | 4,218 | 4,718 | 0 | 0 |
| Phone-around (today) | 96.9% ± 0.5 | 84.9% ± 1.5 | 10.3% | 5.6% | 2,602 | 3,203 | 576 | 2,372 |
| RaktSetu + 7-day average | 99.8% ± 0.2 | 87.2% ± 1.0 | 4.7% | 3.1% | 1,688 | 1,525 | 906 | 4,853 |
| RaktSetu + ML forecast | 99.8% ± 0.2 | 87.4% ± 1.1 | 4.8% | 2.9% | 1,664 | 1,538 | 922 | 5,022 |
| RaktSetu + perfect forecast (bound) | 99.8% ± 0.2 | 88.6% ± 1.3 | 5.0% | 1.5% | 1,507 | 1,410 | 901 | 4,941 |

**vs today's phone-around: 36% fewer unmet requests and 52% fewer expired units**, at the cost of 2,650 more van-km.

### 2025 full year

| Policy | Red-cell fill | Platelet fill | Red-cell wastage | Platelet wastage | Unmet units | Expired units | Trips | km |
|---|---|---|---|---|---|---|---|---|
| Isolated banks | 90.2% ± 0.2 | 83.9% ± 0.7 | 14.9% | 22.8% | 10,009 | 16,015 | 0 | 0 |
| Phone-around (today) | 93.9% ± 0.4 | 93.2% ± 0.7 | 11.6% | 14.3% | 5,592 | 11,764 | 1,972 | 8,071 |
| RaktSetu + 7-day average | 99.8% ± 0.2 | 95.0% ± 0.7 | 5.4% | 12.7% | 1,158 | 6,737 | 3,237 | 18,523 |
| RaktSetu + ML forecast | 99.8% ± 0.2 | 95.2% ± 0.7 | 5.5% | 12.4% | 1,107 | 6,732 | 3,287 | 19,398 |
| RaktSetu + perfect forecast (bound) | 99.8% ± 0.2 | 97.1% ± 0.5 | 5.5% | 10.7% | 745 | 6,368 | 3,163 | 18,930 |

**vs today's phone-around: 80% fewer unmet requests and 43% fewer expired units**, at the cost of 11,327 more van-km.

## 4. Sensitivity: does the conclusion survive different assumptions?

2024 dengue season. Each row changes one assumption; the rest stay at their defaults.

| Assumption | Value | Unmet (today → RaktSetu) | Expired (today → RaktSetu) |
|---|---|---|---|
| Dengue platelet peak (x baseline - 1) | 1.5 | 824 → 129 (-84%) | 4,504 → 3,146 (-30%) |
| Dengue platelet peak (x baseline - 1) | 2.5 | 2,633 → 1,759 (-33%) | 3,211 → 1,662 (-48%) |
| Dengue platelet peak (x baseline - 1) | 4.0 | 7,046 → 6,209 (-12%) | 3,034 → 1,419 (-53%) |
| Collection / demand | 0.98 | 4,633 → 2,835 (-39%) | 2,252 → 320 (-86%) |
| Collection / demand | 1.08 | 2,633 → 1,736 (-34%) | 3,211 → 1,625 (-49%) |
| Collection / demand | 1.18 | 1,278 → 887 (-31%) | 4,502 → 3,448 (-23%) |
| Vans available | 1.0 | 2,633 → 1,754 (-33%) | 3,211 → 1,675 (-48%) |
| Vans available | 2.0 | 2,633 → 1,759 (-33%) | 3,211 → 1,671 (-48%) |
| Vans available | 3.0 | 2,633 → 1,755 (-33%) | 3,211 → 1,645 (-49%) |
| Service quantile protected | 0.7 | 2,633 → 1,728 (-34%) | 3,211 → 1,676 (-48%) |
| Service quantile protected | 0.8 | 2,633 → 1,742 (-34%) | 3,211 → 1,643 (-49%) |
| Service quantile protected | 0.9 | 2,633 → 1,783 (-32%) | 3,211 → 1,614 (-50%) |

## 5. Reproducibility

The optimiser uses 8 parallel CP-SAT workers with a 2% optimality gap, so two identical runs can pick different (equally good) plans. Same run twice:

- `rbc_unmet`: 126 vs 119
- `plt_unmet`: 1702 vs 1707
- `rbc_expired`: 1374 vs 1368
- `plt_expired`: 305 vs 303
- `planned_trips`: 722 vs 733

_Evaluation runtime: 489.9s._
