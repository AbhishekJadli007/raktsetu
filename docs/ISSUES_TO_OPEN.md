# Issues to open on GitHub (Day 3)

Copy each into a GitHub issue. Label the small ones `good first issue`.

1. **Read real stock from an e-RaktKosh export** (`enhancement`)
   Add `raktsetu/connectors/eraktkosh.py` that parses a CSV export of stock by blood group and expiry into the `overrides` format accepted by `engine.todays_plan`. Add a sample file and a test.

2. **ABO-aware platelet issuing** (`enhancement`, `clinical-realism`)
   Platelets are pooled across groups today. Split the `PLT` SKU by ABO group with a preference order for ABO-non-identical issue, and re-run `python -m raktsetu evaluate --quick`.

3. **Hindi interface** (`good first issue`, `frontend`)
   Add an English/हिन्दी toggle in `web/src/App.tsx`. Strings live in the four view files. Start with the Control Room trip cards and escalations.

4. **Fit the dengue lag to weekly case data** (`research`)
   Replace the literature kernel in `world.dengue_shape` with lags fitted to weekly IDSP district dengue counts, if obtainable. Report the change in surge-radar WAPE.

5. **Add a second city** (`good first issue`, `data`)
   Change `BBOX` in `data/fetch_real_data.py`, write a `bank_profiles.csv` for the new city's banks, and document the steps in the README.
