"""Configuration for the PropRadar dashboard pipeline.

The sheet layout below is derived from how ``src/sleeper/saveSleeper.py`` and
``src/prizePicks/savePP.py`` write rows. Each leg of a parlay/entry occupies one
row (columns B-H); the parlay-level profit is written to column I on the final
leg row, followed by a blank separator row.

    B   Date            (%m/%d/%y)
    C   Player
    D   League / sport
    E   Stat            (abbreviated, see saveSleeper.getStatName)
    F   Payout          (Sleeper payout multiplier; empty for PrizePicks)
    G   O/U             ("O" or "U")
    H   Result          ("H" hit, "M" miss, "P" push)
    I   Profit          (parlay-level P/L, only on the last leg row)
    J   Wager           (OPTIONAL stake; not written today, read if present)

The "Random" / "Random Shit" misc P/L columns are intentionally ignored.
"""

WORKBOOK_NAME = "Prize Picks"

# Per-platform worksheet names within the workbook.
SLEEPER_WORKSHEET = "Sleeper Performance"
PRIZEPICKS_WORKSHEET = "Performance Data"

# Column indexes (1-based, matching gspread / A1 columns).
COL_DATE = 2      # B
COL_PLAYER = 3    # C
COL_LEAGUE = 4    # D
COL_STAT = 5      # E
COL_PAYOUT = 6    # F
COL_OU = 7        # G
COL_RESULT = 8    # H
COL_PROFIT = 9    # I
COL_WAGER = 10    # J (optional, read-only)

VALID_RESULTS = {"H", "M", "P"}

# Baseline decimal odds retained for reference. The dashboard's Est. Edge now
# uses a realized formula (avg payout multiplier of hitting picks - 1) rather
# than this baseline, but the value is still surfaced in the exported payload.
FAIR_ODDS_BASELINE = 1.05

# Typical Sleeper stake. Most Sleeper parlays were $10; when an entry has no
# explicit wager (column J) and can't be recovered from the API, assume this so
# ROI counts winning parlays instead of collapsing to losses only.
DEFAULT_SLEEPER_WAGER = 10.0

# Essentially every recorded Sleeper parlay is a single Sleeper promo pick plus
# one or more PropRadar picks. The sheet drops the promo leg, and the API can
# only recover it for recent parlays, so for older/unmatched entries we credit
# one assumed promo leg to keep the real parlay size (avg legs) accurate.
ASSUME_SLEEPER_PROMO_LEG = True

# Number of most-recent entries to surface per platform.
RECENT_LIMIT = 50

# Number of best/worst entries to surface per platform.
TOP_LIST_SIZE = 5

# Optional summary / formula cells in the sheet to surface for cross-checking the
# Python-computed numbers. Populate after auditing the live sheet, e.g.:
#   SLEEPER_SUMMARY_CELLS = {"sheet_total_profit": "A1", "sheet_record": "A2"}
# Cells are read verbatim (formula results) and shown alongside computed values.
SLEEPER_SUMMARY_CELLS: dict[str, str] = {}
PRIZEPICKS_SUMMARY_CELLS: dict[str, str] = {}

# Branding (anonymous public showcase).
SITE_TITLE = "PropRadar"
SITE_TAGLINE = "Sports betting model performance"

# Default output path for the exported dashboard payload, relative to repo root.
DEFAULT_OUTPUT_PATH = "docs/data/stats.json"
