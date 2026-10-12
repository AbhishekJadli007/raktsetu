"""Write the synthetic Jaipur blood network to data/generated/ (seeded, reproducible).

    python data/generate.py            # or: python -m raktsetu generate

Outputs
  generated/daily_bank_sku.csv.gz   requests and new units per day x bank x blood product (2016-2026)
  generated/drivers.csv             real weather, dengue drivers and which dengue years are imputed
  generated/banks.csv               real OSM locations + assumed profiles
  sample/                           the first 30 days of September 2024, small enough to read
See data/ASSUMPTIONS.md for every parameter and its source.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from raktsetu import config as C  # noqa: E402
from raktsetu.world import build_world, to_frames  # noqa: E402


def main():
    w = build_world()
    frames = to_frames(w)
    C.GENERATED.mkdir(parents=True, exist_ok=True)
    sample = C.ROOT / "data" / "sample"
    sample.mkdir(exist_ok=True)
    frames["daily_bank_sku"].to_csv(C.GENERATED / "daily_bank_sku.csv.gz", index=False)
    frames["drivers"].to_csv(C.GENERATED / "drivers.csv", index=False)
    w.banks.to_csv(C.GENERATED / "banks.csv", index=False)
    d = frames["daily_bank_sku"]
    d[(d.date >= "2024-09-01") & (d.date <= "2024-09-30")].to_csv(sample / "daily_bank_sku_2024-09.csv", index=False)
    print(f"seed={w.scenario.seed}  days={len(w.dates)}  banks={w.B}  rows={len(d):,}")
    print(f"wrote {C.GENERATED.relative_to(C.ROOT)}/ and {sample.relative_to(C.ROOT)}/")


if __name__ == "__main__":
    main()
