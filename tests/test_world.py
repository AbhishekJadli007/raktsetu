import numpy as np

from raktsetu import config as C
from raktsetu.world import Scenario, build_world, load_network


def test_network_is_real_and_complete():
    banks, dmin, dkm = load_network()
    assert len(banks) == 18
    assert banks.lat.between(26.7, 27.1).all() and banks.lon.between(75.6, 76.05).all()
    assert (np.diag(dmin) == 0).all() and (dmin[~np.eye(len(banks), dtype=bool)] > 0).all()


def test_world_is_reproducible():
    a = build_world(Scenario(seed=7))
    build_world.cache_clear()
    b = build_world(Scenario(seed=7))
    assert np.array_equal(a.demand, b.demand) and np.array_equal(a.collections, b.collections)


def test_world_sanity():
    w = build_world()
    assert (w.demand >= 0).all() and (w.collections >= 0).all()
    rbc = w.demand[:, :, :8].sum((1, 2)).mean()
    assert 150 < rbc < 230, rbc  # ~190/day for Jaipur (config)
    ratio = w.collections[:, :, :8].sum() / w.demand[:, :, :8].sum()
    assert 1.0 < ratio < 1.2, ratio
    # dengue season: platelet demand in Sep-Oct well above Jan-Mar
    plt = w.demand[:, :, C.PLT].sum(1)
    m = w.dates.month
    assert plt[(m >= 9) & (m <= 10)].mean() > 1.5 * plt[m <= 3].mean()


def test_imputed_dengue_years_are_flagged():
    w = build_world()
    imputed_years = set(w.dates.year[w.dengue_amp_imputed])
    assert imputed_years.isdisjoint(C.RAJASTHAN_DENGUE_CASES)
    assert 2024 not in imputed_years


def test_scenario_events_apply():
    base = build_world()
    w = build_world(Scenario(separator_failure=(("BMCHRC", "2024-09-01", "2024-09-30"),)))
    b, t0, t1 = w.bank_index("BMCHRC"), w.idx("2024-09-01"), w.idx("2024-09-30")
    assert w.collections[t0:t1 + 1, b, C.PLT].sum() == 0
    assert base.collections[t0:t1 + 1, b, C.PLT].sum() > 0
