import numpy as np

from raktsetu import config as C
from raktsetu.optimizer import plan_transfers, take_oldest


def test_take_oldest_takes_from_the_old_end():
    arr = np.array([[0, 5, 3, 2]], dtype=float)  # ages 0..3
    took = take_oldest(arr, np.array([4.0]))
    assert took.tolist() == [[0, 0, 2, 2]]


def _toy(B=4):
    S, A = len(C.SKUS), 36
    inv = np.zeros((B, S, A))
    inv[0, 0, 30] = 40          # bank 0: 40 old O+ units (expiring soon)
    inv[0, C.PLT, 3] = 20       # bank 0: 20 platelets, 1 day left
    mu = np.zeros((B, S, 5))
    mu[0] += 0.2                # bank 0 barely uses anything
    mu[1, 0] = 8.0              # bank 1 needs O+ ...
    mu[1, C.PLT] = 6.0          # ... and platelets
    dmin = np.full((B, B), 10.0)
    np.fill_diagonal(dmin, 0)
    return inv, mu, dmin


def test_plan_moves_surplus_to_need_and_respects_limits():
    inv, mu, dmin = _toy()
    k = np.full(len(C.SKUS), 10.0)
    plan = plan_transfers(inv, mu, k, dmin, vans=1)
    assert plan.transfers, plan.status
    assert all(t.src == 0 and t.dst == 1 for t in plan.transfers)
    moved = {C.SKUS[t.sku]: t.units for t in plan.transfers}
    assert moved.get("O+", 0) > 0 and moved.get("PLT", 0) > 0
    # never more than the receiver needs or the giver can spare
    for t in plan.transfers:
        assert t.units <= plan.need[t.dst, t.sku] and t.units <= plan.give[t.src, t.sku]
    assert len(plan.trips) <= 1 * C.TRIPS_PER_VAN
    assert sum(t.units for t in plan.transfers) <= C.BOX_CAPACITY * len(plan.trips)
    assert plan.at_risk[0, C.PLT] > 0  # the platelets with 1 day left were flagged


def test_no_vans_means_no_plan():
    inv, mu, dmin = _toy()
    plan = plan_transfers(inv, mu, np.full(len(C.SKUS), 10.0), dmin, vans=0)
    assert plan.transfers == []
