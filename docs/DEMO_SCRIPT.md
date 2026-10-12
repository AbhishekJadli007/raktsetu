# Demo video (target 2:45) and defence-call preparation

## Before you record (10 minutes)

1. **Start the server** (skip if it is already running):
   ```bash
   cd ~/Desktop/mujHackathon/raktsetu && source .venv/bin/activate
   uvicorn api.main:app --port 8000
   ```
2. **Open Chrome** at `http://localhost:8000`. Use a clean window: hide bookmarks (**⌘⇧B**), close other tabs, turn on **Do Not Disturb**.
   Make the window full-screen (**⌃⌘F**) and keep browser zoom at 100% (**⌘0**).
3. **Rehearse once without recording**, clicking every step below. Every demo result is precomputed, so each click answers instantly.
4. **Start recording:** press **⌘⇧5** → *Record Entire Screen* → *Options* → Microphone: *MacBook Microphone* → *Record*.
   Stop with the ■ icon in the menu bar. The video is saved to the Desktop.
5. Speak slowly and move the mouse to whatever you are talking about. If you fluff a line, pause, then repeat the sentence. You can trim later in QuickTime (**⌘T**).

## The recording, click by click

| # | Time | Where you are | What you click / do | What you say |
|---|---|---|---|---|
| 1 | 0:00 | **Overview** tab (top of page) | Nothing. Slowly move the mouse over the big headline, then the map on the right with the moving blue lines. | "Hi, I'm Abhishek Jadli, and this is RaktSetu: a bridge for blood. India now collects about as much blood as it needs every year, yet five to fifteen percent of it is wasted. And every dengue season, Jaipur's hospitals run short of platelets, which last only five days. The blood exists. It's just in the wrong bank on the wrong day." |
| 2 | 0:20 | Overview | Hover over the box **"The problem, in one sentence"**. | "My user is the district blood-transfusion coordinator. Today each of Jaipur's eighteen blood banks plans alone, and e-RaktKosh only shows today's stock. Nothing tells the coordinator what to do about it." |
| 3 | 0:30 | Overview | Scroll down slowly through the six red **evidence** cards. Stop before "How it works". | "Every number here links to its source: ORF, BMJ Global Health, NACO data and the national dengue programme." |
| 4 | 0:40 | Top bar | Click **Control Room**. Wait about 1 second for the map. | "This is the coordinator's morning screen. RaktSetu forecasts requests at every bank for the next few days. Then an optimiser picks the van trips that prevent the most shortages and expiries with the vans available." |
| 5 | 0:52 | Control Room KPI cards | Move the mouse across the five cards: **8 van trips · 344 units moved · 170 saved from expiry**. | "This morning: eight trips, 344 units, and 170 units saved from being thrown away." |
| 6 | 1:00 | Right panel, **Transfers** tab | Trip **1. PUSHPA → SMS** is already open. Point at its first two reasons. | "Every trip explains itself. Here, SMS expects about 66 B-positive requests in five days, while Pushpa's B-positive units would expire unused within a week." |
| 7 | 1:12 | Right panel | Click the **Escalations** tab. | "When no bank can spare stock, RaktSetu doesn't hide it. It escalates: arrange platelet donors for these banks." |
| 8 | 1:20 | Map | Click the **SMS** dot (centre of the city, labelled SMS). A panel opens on the left. Scroll inside that panel to **"Type in this bank's real stock"**, type **0** in the **PLT** box, and click **Re-plan with these**. | "A coordinator, or a judge, can type in real stock. Say SMS has no platelets right now… and the whole city is re-planned in seconds." |
| 9 | 1:35 | After re-plan | Point at **Needs donors, not vans** (391 → **431**) and the Escalations list, now topped by **SMS: arrange 74 more platelets**. Then click **Reset** at the bottom of the SMS panel and close it with **X**. | "At the dengue peak no bank can spare platelets, so SMS jumps straight to the top of the escalations: arrange 74 more platelets from donors." |
| 10 | 1:42 | Control Room | Scroll down to the **Platelet surge radar** card. Then scroll back up, click the chip **Jump to: 20 Aug 2024 · before the surge** (just under the Date box). Wait 1 second, then scroll down to the radar again. It turns **ALERT**. | "Moving stock can't fix a city-wide shortage. Rain leads dengue by about eight weeks, so the surge radar reads real Jaipur rainfall. On the 20th of August 2024, it warned that platelet need would reach about 118 a day against 74 produced, three weeks before the September peak. That's enough time to book donors." |
| 11 | 2:02 | Top bar | Click **Simulation Lab**. In **Presets**, click **Everything at once**. | "To test it, I replay the real 2024 dengue season under three policies: banks alone, today's phone-around, and RaktSetu. This is the hardest case: a severe season, a broken platelet machine, a bus accident, and only one van." |
| 12 | 2:14 | Simulation Lab | Point at the three KPI cards (RaktSetu shows **−16%** unmet, **−38%** expired). Scroll a little and press **▶** on **Day-by-day replay**. Let it play about 6 seconds. | "Left is today's practice, right is RaktSetu. Fewer red banks turning patients away, and far less waste." |
| 13 | 2:24 | Top bar | Click **Evidence & Method**. Scroll to **Five policies, five random seeds**, then briefly to the **Sensitivity** table. | "Across five random seeds, RaktSetu cuts unmet requests by 36 percent and expired units by 52 percent compared with phone-around, and that holds for every assumption I varied. To be clear about the limits: demand data is simulated on a real network, most of the gain comes from coordination rather than the ML, and it costs more driving." |
| 14 | 2:42 | Evidence | Scroll to **Limitations, stated before you ask** and stop. | "RaktSetu is open source under MIT, with tests, documentation and a one-command deploy. The next step is a pilot with one district's real stock data. Thank you." |

**After recording:** watch it once. If it runs past 3:00, cut step 3 (evidence scroll) or step 9.
Upload to YouTube as *Unlisted* (or Google Drive with "Anyone with the link") and put the link in your submission and README.

**Optional 15-second extra (terminal):** show that it isn't a mock-up:
`python -m raktsetu plan --date 2024-09-20 --set-stock SMS:PLT:0`

## Defence-call questions we expect

**"Is this real data?"**
The network, roads, weather, dengue years and blood-group mix are real. Per-bank daily requests are generated, because that data isn't public. Every assumption is in `data/ASSUMPTIONS.md`, and the sensitivity analysis varies the important ones.

**"Why not just use e-RaktKosh?"**
e-RaktKosh shows current stock, and 22% of banks rarely update it. It doesn't forecast or recommend. RaktSetu could sit on top of it: the API already accepts typed-in stock.

**"Does your AI beat a baseline?"**
Yes, modestly. Forecast WAPE is 33.2% vs 35.8% (red cells) and 52.8% vs 55.6% (platelets), and the noise floor is 33.1% / 51.5%, so there isn't much more to gain. The surge radar beats persistence by 34–41% at weeks 3–4. Most of the impact comes from the optimiser.

**"Why CP-SAT and not a greedy rule?"**
Trips have a fixed cost and a van limit, and one trip can carry many blood groups. That's a fixed-charge network-flow problem, and an integer programme handles it exactly in about 0.1 s.

**"Why don't 1, 2 or 3 vans give different results?"**
All banks are 6–25 minutes apart, so the optimiser puts the same ~36 units a day into fewer, fuller trips. One van is enough. The bottleneck is information.

**"Why are platelet results worse than red-cell results?"**
At the dengue peak the whole city is short. Sharing can't create platelets, which is why the surge radar exists.

**"Why would private banks give stock away?"**
They never go below their own protected need, and in dengue season every bank is sometimes a receiver. Adoption needs a state mandate or an incentive. That's my main open question.

**"Run it on a date we pick."**
`python -m raktsetu plan --date <any date 2016-07 to 2026-10>`, or use the Control Room date picker. Seeds and scenarios can be changed too.

**"What happens if the solver is slow?"**
There's a 1 s limit with a 2% optimality gap. A feasible plan is returned even when the optimum isn't proven.

**Be ready to explain every part yourself** (you are a solo team, so every question comes to you):
- `world.py`: what is real and what is generated (`data/ASSUMPTIONS.md`)
- `forecast.py`: the features, the time split and the baselines
- `optimizer.py`: the integer programme (written out in `docs/ARCHITECTURE.md`)
- `simulator.py`: the daily loop (transfers → issue → phone-around → donations → expiry)
- `api/main.py` and the four web views
