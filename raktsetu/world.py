"""The simulated Jaipur blood network: real structure + real weather + generated demand and donations.

Real:      bank locations (OpenStreetMap), road travel times (OSRM), daily weather (Open-Meteo),
           annual Rajasthan dengue cases (NCVBDC), blood-group frequencies (Agrawal et al. 2014).
Generated: daily requests per bank and blood group, donations, camps, platelet production.
Everything generated is seeded, so the same Scenario always produces the same world.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as C


# ------------------------------------------------------------------ scenario knobs
@dataclass(frozen=True)
class Scenario:
    """Everything a user (or a judge) can change. All fields have sensible defaults."""

    seed: int = C.SEED
    dengue_scale: float = 1.0          # multiplies the real annual dengue amplitude
    kappa: float = C.DENGUE_PLT_KAPPA  # peak platelet multiplier in a median dengue year
    donation_change: float = 0.0       # e.g. -0.3 = walk-in donations fall 30% (heatwave, curfew)
    change_start: str | None = None    # window in which donation_change applies (None = whole run)
    change_end: str | None = None
    separator_failure: tuple = ()      # ((bank_short, start, end), ...) platelet production stops
    collection_halt: tuple = ()        # ((bank_short, start, end), ...) bank collects nothing
    surge: tuple = ()                  # ((bank_short, date, units), ...) mass-casualty red-cell demand
    vans: int = C.VANS
    collection_ratio: float = C.COLLECTION_TO_DEMAND

    def with_(self, **kw) -> "Scenario":
        return replace(self, **kw)


@dataclass
class World:
    dates: pd.DatetimeIndex
    banks: pd.DataFrame
    drive_min: np.ndarray        # (B, B)
    drive_km: np.ndarray         # (B, B)
    weather: pd.DataFrame        # indexed by date, covers lags before dates[0]
    dengue_shape: np.ndarray     # (T,) 0..1 within-season shape from weather
    dengue_amp: np.ndarray       # (T,) annual amplitude from real case counts
    dengue_amp_imputed: np.ndarray  # (T,) bool, True where the year's case count was imputed
    plt_mult: np.ndarray         # (T,) platelet demand multiplier
    demand: np.ndarray           # (T, B, S) requests
    collections: np.ndarray      # (T, B, S) new units entering inventory
    camps: np.ndarray            # (T, B) units collected at camps
    mu_true: np.ndarray          # (T, B, 2) true expected requests (red cells, platelets): the forecast noise floor
    scenario: Scenario = field(default_factory=Scenario)

    @property
    def B(self) -> int:
        return len(self.banks)

    def idx(self, date) -> int:
        return int(self.dates.get_loc(pd.Timestamp(date)))

    def bank_index(self, short: str) -> int:
        m = self.banks.index[self.banks["short"].str.upper() == short.upper()]
        if len(m) == 0:
            raise ValueError(f"Unknown bank '{short}'. Known: {', '.join(self.banks.short)}")
        return int(m[0])


# ------------------------------------------------------------------ real inputs
@lru_cache(maxsize=1)
def load_network() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    osm = pd.read_csv(C.RAW / "blood_banks_jaipur_osm.csv")
    prof = pd.read_csv(C.ROOT / "data" / "bank_profiles.csv")
    banks = osm.merge(prof, on="osm_id", how="inner", validate="1:1")
    if len(banks) != len(osm):
        missing = set(osm.osm_id) - set(prof.osm_id)
        raise ValueError(f"bank_profiles.csv is missing OSM ids: {missing}")
    banks = banks.sort_values("rbc_w", ascending=False).reset_index(drop=True)
    tm = pd.read_csv(C.RAW / "travel_matrix_osrm.csv")
    pos = {o: i for i, o in enumerate(banks.osm_id)}
    B = len(banks)
    dmin, dkm = np.zeros((B, B)), np.zeros((B, B))
    for r in tm.itertuples():
        i, j = pos[r.from_osm_id], pos[r.to_osm_id]
        dmin[i, j], dkm[i, j] = r.drive_min, r.drive_km
    return banks, dmin, dkm


@lru_cache(maxsize=1)
def load_weather() -> pd.DataFrame:
    w = pd.read_csv(C.RAW / "weather_jaipur_openmeteo.csv", parse_dates=["date"]).set_index("date")
    return w.asfreq("D").interpolate(limit=3)


def dengue_amplitude_by_year(years) -> tuple[dict, dict]:
    real = C.RAJASTHAN_DENGUE_CASES
    med = float(np.median(list(real.values())))
    amp, imputed = {}, {}
    for y in years:
        imputed[y] = y not in real
        amp[y] = real.get(y, med) / med
    return amp, imputed


def dengue_shape(weather: pd.DataFrame) -> pd.Series:
    """Within-season dengue intensity, driven by lagged rainfall and temperature suitability.

    Rain kernel: Gaussian weights over lags, centred at 8 weeks (literature: 8-15 week risk window).
    Temperature: suitability peaks near 29 C over the previous 3 weeks.
    """
    lags = np.arange(0, 121)
    k = np.exp(-0.5 * ((lags - C.DENGUE_RAIN_LAG_MEAN_DAYS) / C.DENGUE_RAIN_LAG_SD_DAYS) ** 2)
    k /= k.sum()
    rain = weather["rain_mm"].fillna(0).to_numpy()
    r_lag = np.convolve(rain, k)[: len(rain)]  # causal: r_lag[t] = sum_l k[l] * rain[t-l]
    t21 = weather["temp_mean_c"].rolling(21, min_periods=1).mean().to_numpy()
    suit = np.exp(-0.5 * ((t21 - C.DENGUE_TEMP_OPT_C) / C.DENGUE_TEMP_SD_C) ** 2)
    raw = pd.Series(r_lag * suit, index=weather.index).rolling(7, min_periods=1).mean()
    # Normalise each complete year to peak 1; an incomplete (current) year uses the median annual peak.
    peaks = raw.groupby(raw.index.year).max()
    complete = [y for y in peaks.index if (raw.index.year == y).sum() >= 365]
    ref = float(np.median(peaks.loc[complete]))
    norm = pd.Series(
        [peaks[y] if y in complete else ref for y in raw.index.year], index=raw.index
    )
    return (raw / norm).clip(0, 1.2) ** 1.5


# ------------------------------------------------------------------ generator
def _nb(rng, mu, k):
    mu = np.maximum(mu, 1e-9)
    return rng.negative_binomial(k, k / (k + mu))


def _in_window(dates, start, end):
    m = np.ones(len(dates), dtype=bool)
    if start:
        m &= dates >= pd.Timestamp(start)
    if end:
        m &= dates <= pd.Timestamp(end)
    return m


@lru_cache(maxsize=16)
def build_world(sc: Scenario = Scenario()) -> World:
    banks, dmin, dkm = load_network()
    weather = load_weather()
    dates = pd.date_range(C.HISTORY_START, weather.index[-1], freq="D")
    T, B, S = len(dates), len(banks), len(C.SKUS)
    rng = np.random.default_rng(sc.seed)

    # --- dengue drivers
    shape = dengue_shape(weather).reindex(dates).to_numpy()
    amp_y, imp_y = dengue_amplitude_by_year(sorted(set(dates.year)))
    amp = np.array([amp_y[y] for y in dates.year]) * sc.dengue_scale
    amp_imp = np.array([imp_y[y] for y in dates.year])
    season = amp * shape                                   # (T,)
    plt_mult = 1.0 + sc.kappa * season
    rbc_mult = 1.0 + C.DENGUE_RBC_KAPPA * season

    dow = np.array(C.DOW_DEMAND)[dates.dayofweek.to_numpy()]
    dow = dow / np.mean(C.DOW_DEMAND)

    # --- requests
    w_rbc = (banks.rbc_w / banks.rbc_w.sum()).to_numpy()
    w_plt = (banks.plt_w / banks.plt_w.sum()).to_numpy()
    mu_rbc = C.NETWORK_RBC_PER_DAY * np.outer(dow * rbc_mult, w_rbc)       # (T, B)
    mu_plt = C.NETWORK_PLT_PER_DAY * np.outer(dow * plt_mult, w_plt)
    rbc_total = _nb(rng, mu_rbc, C.NB_K["RBC"])
    pop_share = np.array([C.GROUP_SHARE[g] for g in C.RBC_GROUPS])
    bank_share = rng.dirichlet(pop_share * 600, size=B)                     # small local differences
    demand = np.zeros((T, B, S), dtype=np.int32)
    demand[:, :, :8] = rng.multinomial(rbc_total, bank_share[None, :, :])
    demand[:, :, C.PLT] = _nb(rng, mu_plt, C.NB_K["PLT"])

    for short, day, units in sc.surge:  # mass-casualty event: mostly O and the local mix
        b, t = _bank(banks, short), dates.get_loc(pd.Timestamp(day))
        extra = rng.multinomial(int(units), 0.5 * bank_share[b] + 0.5 * np.eye(8)[0])  # half O+ (index 0)
        demand[t, b, :8] += extra

    # --- donations
    month = dates.month.to_numpy()
    summer = np.where(np.isin(month, [5, 6]), 1 - C.SUMMER_DONATION_DIP, 1.0)
    winter = np.where(np.isin(month, [12, 1, 2]), 1.05, 1.0)
    donor_response = 1.0 + 0.25 * np.minimum(season, 1.5)   # replacement donors & drives in dengue season [GUESS]
    walk_season = summer * winter * donor_response
    change = np.where(_in_window(dates, sc.change_start, sc.change_end), 1 + sc.donation_change, 1.0)

    camp_banks = banks.runs_camps.to_numpy().astype(bool)
    camp_season = np.where(np.isin(month, [12, 1, 2]), 1.5, np.where(np.isin(month, [5, 6]), 0.5, 1.0))
    camp_on = (rng.random((T, B)) < C.CAMP_RATE_PER_DAY * camp_season[:, None]) & camp_banks[None, :]
    for m, d in C.CAMP_DAYS:
        hit = (month == m) & (dates.day.to_numpy() == d)
        camp_on[hit] |= camp_banks
    camps = np.where(camp_on, rng.integers(C.CAMP_SIZE[0], C.CAMP_SIZE[1] + 1, size=(T, B)), 0)

    # Replacement donors: a family member donates at the treating bank, roughly a day after the request.
    prev_rbc = np.vstack([rbc_total[:1], rbc_total[:-1]])
    replacement = rng.binomial(prev_rbc, min(0.95, C.REPLACEMENT_SHARE * sc.collection_ratio))

    # Calibrate voluntary walk-ins so total collection = collection_ratio x expected red-cell demand.
    target = sc.collection_ratio * mu_rbc.sum(axis=1).mean()
    walk_scale = (target - camps.sum(axis=1).mean() - replacement.sum(axis=1).mean()) / walk_season.mean()
    # [GUESS] Banks partly plan donation drives around their own usage: blend collection share toward demand share.
    w_coll = 0.5 * (banks.coll_w / banks.coll_w.sum()).to_numpy() + 0.5 * w_rbc
    lam = np.outer(walk_season * change, w_coll) * walk_scale
    donations = rng.poisson(np.maximum(lam, 0)) + camps + replacement         # whole-blood units (T, B)

    plt_yield = np.minimum(0.75, np.outer(1 + 1.2 * np.minimum(season, 1.5), banks.plt_yield.to_numpy()))
    for short, s, e in sc.collection_halt:
        b, m = _bank(banks, short), _in_window(dates, s, e)
        donations[m, b] = 0
    for short, s, e in sc.separator_failure:
        b, m = _bank(banks, short), _in_window(dates, s, e)
        plt_yield[m, b] = 0.0

    collections = np.zeros((T, B, S), dtype=np.int32)
    collections[:, :, :8] = rng.multinomial(donations, pop_share)
    collections[:, :, C.PLT] = rng.binomial(donations, plt_yield)

    return World(
        dates=dates, banks=banks, drive_min=dmin, drive_km=dkm, weather=weather,
        dengue_shape=shape, dengue_amp=amp, dengue_amp_imputed=amp_imp, plt_mult=plt_mult,
        demand=demand, collections=collections, camps=camps,
        mu_true=np.stack([mu_rbc, mu_plt], axis=-1), scenario=sc,
    )


def _bank(banks: pd.DataFrame, short: str) -> int:
    m = banks.index[banks["short"].str.upper() == str(short).upper()]
    if len(m) == 0:
        raise ValueError(f"Unknown bank '{short}'. Known: {', '.join(banks.short)}")
    return int(m[0])


def to_frames(w: World) -> dict[str, pd.DataFrame]:
    """Long-format tables for data/generated/ (what a judge can open in a spreadsheet)."""
    T, B, S = w.demand.shape
    idx = pd.MultiIndex.from_product([w.dates, w.banks.short, C.SKUS], names=["date", "bank", "sku"])
    long = pd.DataFrame({"requests": w.demand.reshape(-1), "new_units": w.collections.reshape(-1)}, index=idx).reset_index()
    drivers = pd.DataFrame({
        "date": w.dates,
        "rain_mm": w.weather["rain_mm"].reindex(w.dates).to_numpy(),
        "temp_mean_c": w.weather["temp_mean_c"].reindex(w.dates).to_numpy(),
        "dengue_shape": w.dengue_shape.round(4),
        "dengue_amplitude": w.dengue_amp.round(3),
        "dengue_amplitude_imputed": w.dengue_amp_imputed,
        "platelet_demand_multiplier": w.plt_mult.round(3),
    })
    return {"daily_bank_sku": long, "drivers": drivers}
