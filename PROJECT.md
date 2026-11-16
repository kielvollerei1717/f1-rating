# F1 Driver Ratings — Project Log

Data-driven driver & constructor ratings for F1 1990–2026. Built from race results only, no expert votes.

**Live:** https://kielvollerei1717.github.io/f1-rating/
**Repo:** https://github.com/kielvollerei1717/f1-rating

## Status

| Component | State |
|---|---|
| Model (Bradley–Terry fit) | ✅ done |
| 216 drivers + 424 car-seasons | ✅ done |
| Static site | ✅ done |
| GitHub Pages + auto-update | ✅ live |
| Weekly auto re-fit (f1db release) | ✅ scheduled |
| Telemetry integration | ❌ not available for this span (no structured public data before 2018) |
| Driver bio (karting / WEC / GT / MotoGP / Dakar) | ✅ done (Wikipedia cache, 20 seeded, rest via CI) |
| Auto-update ~2 days after race day | ✅ scheduled (Mon 09:00 UTC) |
| Sprint-race / fastest-lap leaderboards | ⏳ not yet |
| Public JSON API endpoint | ⏳ not yet |

## Data

- **Source:** [f1db](https://github.com/f1db/f1db) SQLite, latest release `v2026.20.0` (9 Nov 2026). 74MB, 31 tables.
- **Window:** every classified race finish 1990–2026. **685 races** (688 in the DB; 3 have no RACE_RESULT rows). **216 distinct drivers**, **424 car-seasons**.
- **Cross-checked** 2026 race count and driver list against the Jolpica/Ergast API: race counts match exactly (688=688); driver coverage is a superset (f1db includes test-driver entries that Jolpica excludes).
- **No telemetry.** f1db has no speed/throttle/brake/gear/sector columns anywhere in the schema. Fastest-lap time is the finest public granularity available; treated as a race outcome, not as a performance input.

## Model

Pairwise Bradley–Terry (Elo family). Every race finish is a duel against every other classified finisher in the same race:

```
logit P(i beats j) = (driver_i − driver_j) + (car_i − car_j)
```

Car effect cancels inside a team, so teammate duels isolate driver skill; cross-team results isolate car strength. Two parameters per driver (skill) plus one per `(constructor, year)` (car). Fit with Adam over **83,472 duels**; calibrated priors `N(0, 0.65²)` on skill and `N(0, 0.50²)` on car; converged logloss **0.393**.

Era-fairness: every driver's skill is also measured as a **z-score against the field of their own seasons**, so a 1992 Williams driver and a 2026 Mercedes driver are judged against their own peers, not against each other.

### OVR formula (0–100)

| Component | Weight |
|---|---|
| Career Elo (percentile) | 23% |
| Peak Elo (best rolling 3-season) | 16% |
| Consistency (finish-rate + top-10 rate) | 13% |
| Era-relative z | 13% |
| Excess over average car, era-normalized | 11% |
| Teammate H2H (quali + race) | 9% |
| Era-normalized points (per season, divided by champion's haul) | 9% |
| Raw points per start | 3% |
| Podium rate | 3% |

Deliberately absent: career length, start count, season count. Volume is not a rating input.

### Provisional flag

`PROV` badge when `<10 starts` (small sample) or debut in the last two seasons (early career). It is a caution, not a penalty. 42 of 216 flagged.

## What's on the page

- **Drivers** tab — 216 cards, sortable (career/peak/Elo/wins/titles/starts), filter by decade, nation, search. Click a card: season skill trajectory, rating & machinery, consistency bar, style tags, full H2H vs every teammate (quali + race split), full career record incl. pre-1990. **VS button** on each card jumps to the compare tab with that driver pre-loaded.
- **Cars** tab — all 424 constructor-seasons, searchable/filterable, unclassified ones (Simtek 1994, Forti 1995–96, Minardi 1996–98, …) marked **NC**.
- **VS** tab — pick any two drivers (or use a card's VS button). Side-by-side rating, peak, car, excess, consistency, points, confidence, full record, style tags, and head-to-head if they were teammates. Winner of each metric highlighted.
- **Method** tab — what each column means, what does *not* decide the ranking, who is rated, limits, source.

## Navigation

Keyboard: `1`–`4` switch tabs, `/` focus search, `Esc` close detail. Share button copies a deep link (`#tab?v=<driver>`). Deep-linking a driver card works via `?v=...`.

## Key results (as of last run)

Top career OVR:

1. Verstappen 98.0
2. Prost 96.1
3. Alonso 96.1
4. Leclerc 95.6
5. Norris 95.5
6. Schumacher 95.5
7. Rosberg 93.9
8. Russell 93.8
9. Hamilton 92.8
10. Sainz 92.7

Top car: 2011 Red Bull (Elo 2047).
Bottom: pay-driver era backmarkers (Chilton, Belmondo, Rosset, Dalmas, Grouillard) — expected, sanity check passes.

## Run locally

```
pip install -r requirements.txt
python update.py       # downloads latest f1db, re-fits, regenerates data.js
start index.html       # or python -m http.server
```

## Auto-update

`.github/workflows/update.yml`:

- **Schedule:** Mondays 09:00 UTC — ~2 days after the Sunday race weekend, giving FIA time to post penalties and the official classification to f1db.
- **Manual:** GitHub → *Actions* → *Run workflow*.
- **What it does:** `update.py` (f1db → ratings.json, with GITHUB_TOKEN auth) → `bio.py` (Wikipedia → bios.json, 216 drivers) → `prep.py` (ratings + bios → data.js) → commit diff → Pages auto-deploy.
- **Note:** bio.py runs in CI because the local IP gets Wikipedia-throttled. The Actions runner has a separate IP.

## Known issues / next steps

- **No telemetry** for 1990–2018 (data does not exist publicly in structured form). FastF1 / OpenF1 can add 2018+ lap telemetry as a separate layer.
- **Sprint races** are in the DB but not yet a leaderboard.
- **JSON API** could be exposed via GitHub Pages + a static JSON endpoint (already there as `ratings.json`) or a serverless function.
- **f1db release lag** — ratings track f1db, not live F1. Between releases the site is static.

## Files

| File | Role |
|---|---|
| `index.html` | static site (all UI) |
| `data.js` | trimmed driver + car data (666KB) |
| `ratings.json` | full model output (1.1MB) |
| `model.py` | fit pipeline |
| `prep.py` | trim model output → `data.js` |
| `update.py` | f1db fetch + rebuild |
| `bio.py` | Wikipedia bio scraper (karting, WEC, GT, MotoGP, Dakar) |
| `bios.json` | cached driver bios (committed, regenerated weekly) |
| `.github/workflows/update.yml` | weekly auto-update |
