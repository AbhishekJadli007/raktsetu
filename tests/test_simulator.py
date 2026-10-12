import numpy as np
import pytest

from raktsetu.engine import forecaster
from raktsetu.simulator import simulate
from raktsetu.world import build_world


@pytest.mark.parametrize("policy", ["isolated", "reactive", "raktsetu"])
def test_conservation(policy):
    w = build_world()
    f = forecaster("ma7") if policy == "raktsetu" else None
    r = simulate(w, "2024-09-01", "2024-09-14", policy, f)
    assert np.allclose(r.served + r.unmet, r.demand)
    assert (r.unmet >= -1e-9).all() and (r.stock >= -1e-9).all() and (r.expired >= 0).all()
    # units moved between banks never appear from nowhere
    assert all(t["units"] > 0 and t["src"] != t["dst"] for t in r.transfers)


def test_raktsetu_beats_phone_around_in_dengue_season():
    w = build_world()
    a = simulate(w, "2024-09-01", "2024-10-15", "reactive").kpis(w.banks, w.drive_km)
    b = simulate(w, "2024-09-01", "2024-10-15", "raktsetu", forecaster("ml")).kpis(w.banks, w.drive_km)
    assert b["total_unmet"] < a["total_unmet"]
    assert b["total_expired"] < a["total_expired"]
