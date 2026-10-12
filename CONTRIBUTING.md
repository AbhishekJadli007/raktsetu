# Contributing to RaktSetu

Thank you for helping. RaktSetu is a research prototype; the most valuable contributions bring it closer to real use.

## Set up

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                  # 15 tests, ~10 s
python -m raktsetu plan --date 2024-09-20
```

Web app: `cd web && npm install && npm run dev` (with `uvicorn api.main:app --port 8000` running).

## Propose a change

1. Open an issue describing the problem (or pick an existing one, especially `good first issue`).
2. Fork, branch (`feature/short-name`), commit small steps with clear messages.
3. Run `pytest` and, if you touched the model, `python -m raktsetu evaluate --quick`.
4. Open a pull request saying what changed and how you checked it.

## Rules that keep the project honest

- **Never present generated data as real.** New parameters go in `raktsetu/config.py` with a `[SOURCE]` or `[GUESS]` tag and a row in `data/ASSUMPTIONS.md`.
- **Every model change is compared with its baseline** and the numbers go in `docs/EVALUATION.md` (regenerate it, don't hand-edit).
- **Keep runs reproducible:** seeds stay fixed, and generation code is committed, not only its output.
- **No secrets in the repo.** There are none today; if you add an API, use `.env` (ignored) and document the variable in `.env.example`.

## Where help is most useful

- **Real data:** a connector that reads stock from e-RaktKosh (or a CSV export) into `engine.todays_plan(overrides=...)`.
- **Clinical realism:** ABO-aware platelet issuing, apheresis capacity, cross-match reservations.
- **Dengue signal:** fit the rainfall lag to weekly district case data (IDSP) instead of the literature kernel.
- **Other cities / products:** a second city config; medicines in public health facilities (same structure).
- **Frontend:** Hindi interface; accessibility review; offline-friendly mobile view for bank staff.

## Code style

Python: type hints where they help, functions over classes, numpy-vectorised where it matters. Keep modules small and named for what they do.
TypeScript: functional components, Tailwind utility classes, design tokens in `web/src/index.css`.
