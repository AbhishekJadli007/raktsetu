# Round 1 — Sections A, B, C

## A. Initial idea

Blood banks in an Indian city run short of blood while others throw blood away. Build an AI that predicts blood demand at each bank and suggests where to send surplus blood.

## B. Refined idea, after feedback

We asked an AI assistant to attack the idea as a sceptical judge, checked every factual claim it produced against a source, and tested the idea against our own simulation. What changed:

| Feedback / finding | What we changed |
|---|---|
| "Is there actually a shortage, or is it a distribution problem?" | We checked: national collection (14.6M) now roughly matches requirement (ORF 2025), so we framed it as **distribution**, matching the oxygen-crisis pattern in the case studies. |
| "A demand forecast alone does not change a decision." | The core became an **optimiser** that outputs van trips. The forecast is an input, not the product. |
| "Which city, which product, which month?" | Narrowed to **Jaipur's 18 blood banks** (real OSM locations), **platelets in dengue season** (5-day shelf life) plus red cells (35 days). |
| "You have no real per-bank data." | A hybrid: real network, roads, weather and dengue years; generated demand with every assumption in `data/ASSUMPTIONS.md` and a sensitivity analysis. |
| "Your baseline is a straw man." | Our first baseline gave 27% wastage, above the reported 5–15%. We added **replacement donors** (30% of supply, ORF) and demand-aware collection until the phone-around baseline produced ~11% wastage, inside the reported range. Our improvement is measured against that realistic baseline. |
| "Does the ML forecast actually matter?" | We measured it honestly: it beats the 7-day average, but **most of the gain is coordination**. A perfect forecast adds little more. |
| "Sharing can't help if the whole city is short." | True at the dengue peak. We added a **surge radar** (rain lags dengue ~8 weeks) to warn 2–4 weeks ahead and trigger donor drives. It beats persistence at weeks 2–4, not at week 1, and we say so. |
| "Why would private, NGO and government banks share?" | Not fully answerable in software. Plans never take a bank below its own protected need, and every bank is a receiver at some point. Adoption needs a state-level mandate. Listed as our main limitation. |

**Refined problem:** Blood-bank coordinators in Jaipur cannot move stock to where it will be needed before it runs out or expires, because each bank plans alone and e-RaktKosh only shows today's stock, which causes platelet shortages in dengue season while units are discarded unused a few kilometres away.

## C. Prototype

- **Input:** a date (optionally real stock, vans, a crisis). **Output:** today's van trips with reasons, shortfalls escalated to donors, a 4-week platelet surge warning.
- **Methods:** gradient-boosted demand forecast vs 7-day-average baseline; CP-SAT integer programme for transfers; day-by-day inventory simulator; city-level surge radar.
- **Evaluation:** 5 seeds × 2 windows × 5 policies, sensitivity on 4 assumptions, forecast WAPE vs baselines with a noise floor.
- **Interfaces:** CLI (`python -m raktsetu plan/radar/simulate`), FastAPI, React control room with a live map, a scenario lab and an evidence page.
