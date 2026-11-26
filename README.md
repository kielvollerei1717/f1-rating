# F1 Driver Ratings (1990–2026)

Data-driven driver and constructor ratings built from every classified race finish in **f1db** (`v2026.20.0+`). No expert votes, no reputation.

**[Live site](https://kielvollerei1717.github.io/f1-rating/)**

## Model

Every race finish is turned into pairwise duels against all other classified finishers of the same race. A joint Bradley–Terry (Elo-family) model fits a skill parameter per driver and a car strength per `(constructor, year)`:

```
logit P(i beats j) = (driver_i - driver_j) + (car_i - car_j)
```

Teammates drive the same car, so `car_i - car_j = 0` inside a team — teammate duels isolate driver skill; cross-team results isolate car strength.

- **216 drivers** (every driver with ≥1 race start in 1990–2026; `<10` starts or debuted in last 2 seasons flagged `PROV`)
- **424 car-seasons** (including unclassified/zero-point teams marked `NC`)
- **83,643 race duels** across 686 races
- Career length / race count is deliberately excluded from the rating formula

## Auto-update

GitHub Actions (`.github/workflows/update.yml`) runs every Monday at 06:00 UTC (or manually via **Actions → Run workflow**): fetches the latest [f1db](https://github.com/f1db/f1db) SQLite release, re-fits `model.py`, regenerates `data.js`, commits any diff, and deploys to GitHub Pages.

## Run locally

```bash
pip install -r requirements.txt
python update.py   # downloads latest f1db release and rebuilds data.js
```

Then open `index.html` (or serve the folder with `python -m http.server`).
