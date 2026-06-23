# PropRadar Dashboard

Builds the performance data shown by the static site in [`docs/`](../../docs).
It reads the Google Sheets workbook (Sleeper + PrizePicks worksheets), computes
analytics, and writes a single JSON payload to
[`docs/data/stats.json`](../../docs/data/stats.json).

## Regenerate the data

From the repo root:

```bash
python -m src.dashboard.export
```

On success it prints `dashboard: exported stats to .../docs/data/stats.json`.

## Prerequisites

- **`googlesheets-credentials.json`** in the repo root (required — the export
  fails without it).
- Network access to Google Sheets.

## Notes

- The export also runs automatically at the end of the recording scripts
  (`src/sleeper/saveSleeper.py`, `src/prizePicks/savePP.py`). Set
  `DASHBOARD_EXPORT=0` to skip it during recording.
- Preview the site locally:

  ```bash
  cd docs && python3 -m http.server 8000
  # open http://localhost:8000
  ```
