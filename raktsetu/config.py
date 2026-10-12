"""Every tunable number in RaktSetu lives here, next to where it came from.

Values tagged [SOURCE] come from a cited document (see data/ASSUMPTIONS.md).
Values tagged [GUESS] are our assumptions; the sensitivity analysis varies the important ones.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
GENERATED = ROOT / "data" / "generated"
ARTIFACTS = ROOT / "artifacts"
# Trained models live here; override with RAKTSETU_MODEL_DIR (e.g. a writable folder on a host).
MODEL_DIR = Path(os.environ.get("RAKTSETU_MODEL_DIR", ARTIFACTS))

SEED = 42

# ---------------------------------------------------------------- products
RBC_GROUPS = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"]
SKUS = RBC_GROUPS + ["PLT"]  # 8 red-cell groups + platelets
PLT = len(SKUS) - 1

# [SOURCE] Agrawal et al. 2014, Asian J Transfus Sci 8(2):121-125, n=10,000 donors across India.
ABO_SHARE = {"O": 0.3712, "A": 0.2288, "B": 0.3226, "AB": 0.0774}
RH_POS = 0.9461
# [GUESS] Rh assumed independent of ABO (the paper does not publish the cross-tab in text).
GROUP_SHARE = {g: ABO_SHARE[g[:-1]] * (RH_POS if g.endswith("+") else 1 - RH_POS) for g in RBC_GROUPS}

# [SOURCE] Standard storage limits: red cells in CPDA-1 = 35 days, platelets at 20-24 C = 5 days.
SHELF_DAYS = {"RBC": 35, "PLT": 5}

# Red-cell compatibility, recipient -> acceptable donor groups in order of preference.
# O- is listed last everywhere because it is the scarcest universal-donor stock.
RBC_COMPATIBLE = {
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}

# ---------------------------------------------------------------- network demand / supply scale
# [GUESS, order-of-magnitude check] India needs ~14.6M units/yr for ~1.4B people (ORF 2025) = ~10.4 per 1,000.
# Jaipur district ~6.6M people (Census 2011) -> ~190 units/day. Jaipur is also a referral hub, so this is conservative.
NETWORK_RBC_PER_DAY = 190.0
NETWORK_PLT_PER_DAY = 45.0  # [GUESS] baseline platelet units/day outside dengue season
# [SOURCE-ish] National collection now roughly matches requirement (ORF 2025). We let collection run 8% above demand.
COLLECTION_TO_DEMAND = 1.08
# [SOURCE] ~30% of India's supply comes from replacement donors (patients' families), ~70% voluntary (ORF 2025).
# Replacement donors give at the bank treating their relative, which partly balances each bank on its own.
REPLACEMENT_SHARE = 0.30

# Day-of-week demand factor (Mon..Sun). [GUESS] fewer elective surgeries on Sundays.
DOW_DEMAND = [1.06, 1.04, 1.03, 1.03, 1.02, 0.98, 0.84]

# Negative-binomial dispersion of daily requests (var = mu + mu^2/k). [GUESS]
NB_K = {"RBC": 12.0, "PLT": 6.0}

# ---------------------------------------------------------------- dengue
# [SOURCE] Rajasthan annual dengue cases, NCVBDC (2021-2025) and Rajya Sabha answer (2015-2017).
RAJASTHAN_DENGUE_CASES = {2015: 4043, 2016: 5292, 2017: 8387, 2021: 20749, 2022: 13491, 2023: 13924, 2024: 12514, 2025: 4348}
# Years without a published figure we could retrieve are imputed with the median of the real years and FLAGGED.
# [SOURCE] Lag structure: pan-India study (Cambridge Epidemiol Infect 2019) found rainfall risk peaks at 8-15 week lags,
# temperature risk peaks near 30 C at 0-3 week lags; Delhi/Bhopal studies report ~2 month lags.
DENGUE_RAIN_LAG_MEAN_DAYS = 56   # centre of the rainfall lag kernel (8 weeks)
DENGUE_RAIN_LAG_SD_DAYS = 21
DENGUE_TEMP_OPT_C = 29.0
DENGUE_TEMP_SD_C = 4.5
# [GUESS] In a median dengue year, peak platelet demand reaches (1 + KAPPA) x baseline.
# Jaipur press reports describe far larger jumps at individual banks; we stay conservative and vary it in sensitivity.
DENGUE_PLT_KAPPA = 2.5
DENGUE_RBC_KAPPA = 0.08  # small spill-over into red-cell demand [GUESS]

# ---------------------------------------------------------------- donations
SUMMER_DONATION_DIP = 0.22  # [GUESS] May-June walk-in donations fall (heat, colleges closed)
CAMP_RATE_PER_DAY = 0.035   # [GUESS] probability an NGO/camp-running bank holds a camp on a given day
CAMP_SIZE = (40, 120)       # [GUESS] units collected per camp
# [SOURCE] National Voluntary Blood Donation Day (1 Oct) and World Blood Donor Day (14 Jun): large camps.
CAMP_DAYS = [(10, 1), (6, 14)]

# ---------------------------------------------------------------- logistics / policy
VANS = 2                 # [GUESS] vehicles a district coordinator can dispatch per day
TRIPS_PER_VAN = 4
BOX_CAPACITY = 50        # units per insulated transport box/trip
PLAN_HORIZON = {"RBC": 5, "PLT": 3}   # days of demand the plan protects
SERVICE_QUANTILE = 0.8   # protect each bank against its 80th-percentile demand
REACTIVE_NEIGHBOURS = 3  # a bank in trouble phones its 3 nearest banks
REACTIVE_COMFORT_DAYS = 3.0  # a bank only lends what it holds beyond 3 days of its own usage
MAX_DRIVE_MIN = 60
CANDIDATE_SUPPLIERS = 5     # each short bank considers its 5 nearest banks with spare stock
SOLVER_WORKERS = 8          # parallel CP-SAT: ~0.1 s/day on a laptop (see docs/ARCHITECTURE.md)
SOLVER_TIME_LIMIT_S = 1.0
SOLVER_GAP = 0.02           # accept plans within 2% of the proven optimum

# Optimiser weights (value per unit moved, in "units of unmet demand avoided").
W_UNIT = {"RBC_POS": 1.0, "RBC_NEG": 2.0, "PLT": 3.0}
W_EXPIRY_SAVED = 1.0
TRIP_FIXED_COST = 1.5
TRIP_COST_PER_MIN = 0.08

# ---------------------------------------------------------------- time windows
HISTORY_START = "2016-03-01"   # first day of synthetic history (weather from 2016-01-01 feeds the lags)
TRAIN_END = "2022-12-31"
VALID_END = "2023-12-31"
TEST_YEARS = [2024, 2025]
