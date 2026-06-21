# PropRadar Dashboard

Builds the performance data shown by the static site in [`docs/`](../../docs).
It reads the Google Sheets workbook (Sleeper + PrizePicks worksheets), enriches
Sleeper entries with promo-leg data from the Sleeper API, computes analytics, and
writes a single JSON payload to [`docs/data/stats.json`](../../docs/data/stats.json).

## Regenerate the data

From the repo root:

```bash
python -m src.dashboard.export
```

On success it prints `dashboard: exported stats to .../docs/data/stats.json`.

## Prerequisites

- **`googlesheets-credentials.json`** in the repo root (required — the export
  fails without it).
- **`SLEEPER_AUTH`** in your `.env` file (used to recover promo legs and
  authoritative profit/wager from the API). This token expires periodically;
  refresh it by copying the cookie from a real Sleeper request.
  - Valid: recent parlays get their real promo legs and exact profit/wager.
  - Missing/expired: the export still succeeds, falling back to an assumed
    single promo leg and the `$10` default stake. You'll see a
    `sleeper_enrich: could not fetch parlays ...` log line.
- Network access to Google Sheets and the Sleeper API.

## Notes

- The export also runs automatically at the end of the recording scripts
  (`src/sleeper/saveSleeper.py`, `src/prizePicks/savePP.py`). Set
  `DASHBOARD_EXPORT=0` to skip it during recording.
- Preview the site locally:

  ```bash
  cd docs && python3 -m http.server 8000
  # open http://localhost:8000
  ```
