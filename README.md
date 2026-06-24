# PropRadar

PrizePicks and Sleeper betting automation and odds analysis.

Live performance dashboard: [shamby87.github.io/PropRadar](https://shamby87.github.io/PropRadar/).

## Requirements

- Python >= 3.11
- pip

## Setup

1. **Create a virtual environment** (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install the package**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Create `.env`** from the example:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your credentials (see [Environment Variables](#environment-variables) below).

4. **For Google Sheets integration** (save scripts and dashboard):
   - Create a service account in Google Cloud Console
   - Download the JSON credentials file
   - Save as `googlesheets-credentials.json` in the repo root (gitignored)

## Environment Variables

Create `.env` in the repo root with the following variables:

```bash
cp .env.example .env
```

See `.env.example` for the full list. Required for most scripts:

| Variable | Purpose |
|----------|---------|
| `API_KEYS` | Comma-separated keys from [the-odds-api.com](https://the-odds-api.com) |
| `PRIZEPICKS_COOKIE` | Cookie header from logged-in PrizePicks API requests |
| `SLEEPER_AUTH` | Authorization header from Sleeper API requests |
| `PARLAY_WEBHOOK` | Discord webhook for parlays |
| `ADMIN_WEBHOOK` | Discord webhook for admin notifications |
| `SLEEPER_PLAYS_WEBHOOK` | Discord webhook for Sleeper plays |
| `ADMIN_ID` | Discord user ID |
| `SLEEPER_ROLE_ID` | Discord role ID |

Optional: `SLEEPER_LEAGUE_ID` (sharing parlays), `SLEEPER_DRY_RUN` (log without submitting).

## Commands

All commands run from the repo root. Arguments: `league` (NFL, NBA, CBB, NHL, MLB), `start_day` and `end_day` as offsets from today (0 = today, 1 = tomorrow, -1 = yesterday).

### Analysis

Compare PrizePicks and Sleeper lines against sportsbook odds:

```bash
python -m src.prizePicks.pp NBA 0 3        # PrizePicks lines for next 3 days
python -m src.sleeper.sleeper NBA 0 3      # Sleeper lines for next 3 days
```

Use `--from-file` to read PrizePicks from `data.txt` instead of the API.

### Automation

Auto-place Sleeper parlays:

```bash
python -m src.sleeper.autoSleeper NBA 0 3              # Submit parlays
python -m src.sleeper.autoSleeper NBA 0 3 --dry-run    # Log without submitting
```

### Record Results

Save settled entries to Google Sheets (requires `googlesheets-credentials.json`):

```bash
python -m src.prizePicks.savePP 01/01/25       # PrizePicks results (MM/DD/YY)
python -m src.sleeper.saveSleeper 01/01/25     # Sleeper results (MM/DD/YY)
```

### Dashboard

Published at [shamby87.github.io/PropRadar](https://shamby87.github.io/PropRadar/). To regenerate data locally:

```bash
python -m src.dashboard.export                # Export JSON to docs/data/stats.json
cd docs && python3 -m http.server 8000        # Serve at http://localhost:8000
```

See `src/dashboard/README.md` for dashboard details.

## Testing

```bash
pytest      # Run all tests With coverage report
```
