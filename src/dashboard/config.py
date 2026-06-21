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
    J   Wager           (parlay-level stake; written on the last leg row)

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
COL_WAGER = 10    # J

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

# League-column markers that saveSleeper.py writes for Sleeper-provided promo
# legs (see saveSleeper.getPromoLeague). The sheet reader upper-cases the league
# column, so these are stored upper-cased. Legs in any of these "leagues" are
# routed into promo_legs and excluded from PropRadar sport/stat/hit-rate views.
PROMO_LEAGUE_MARKERS = {"OVER BOOST", "LINE DISCOUNT", "PROMO"}

# Minimum number of legs a league must have to be shown in the league-based
# views (the "Hit Rate by League" chart and the per-sport "By Stat" groups).
# Leagues below this are hidden as too small a sample to be meaningful.
MIN_LEAGUE_LEGS = 50

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

# Full, human-readable stat names. Keys are lower-cased so the many source
# spellings/abbreviations (e.g. "Pts"/"Points", "Rush Yards"/"Rush yards") all
# collapse onto one display name. Unmapped stats fall back to a prettified form.
STAT_FULL_NAMES = {
    # NBA / WNBA
    "pts": "Points",
    "points": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "pa": "Points + Assists",
    "pr": "Points + Rebounds",
    "ra": "Rebounds + Assists",
    "ar": "Assists + Rebounds",
    "pra": "Points + Rebounds + Assists",
    # NFL
    "comp": "Pass Completions",
    "completions": "Pass Completions",
    "pass yards": "Passing Yards",
    "passing_touchdowns": "Passing Touchdowns",
    "anytime_touchdowns": "Anytime Touchdowns",
    "rec": "Receptions",
    "receptions": "Receptions",
    "rec yards": "Receiving Yards",
    "rush yards": "Rushing Yards",
    # NHL
    "sog": "Shots on Goal",
    # MLB
    "k": "Strikeouts",
    "strikeouts": "Strikeouts",
    "outs": "Outs Recorded",
    "er": "Earned Runs",
    "hits": "Hits",
    "bases": "Total Bases",
    "hrrbi": "Hits + Runs + RBIs",
}


def full_stat_name(stat: str | None) -> str:
    """Map a raw stat abbreviation to its full display name."""
    if not stat:
        return "Unknown"
    key = stat.strip().lower()
    if key in STAT_FULL_NAMES:
        return STAT_FULL_NAMES[key]
    return stat.replace("_", " ").strip().title()


# Branding (anonymous public showcase).
SITE_TITLE = "PropRadar"
SITE_TAGLINE = "Sports betting model performance"

# Default output path for the exported dashboard payload, relative to repo root.
DEFAULT_OUTPUT_PATH = "docs/data/stats.json"
