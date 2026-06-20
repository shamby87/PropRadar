"""Shared league config and helpers for fixture fetch scripts."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures"

LEAGUES = {
    "NBA": {
        "sport_key": "basketball_nba",
        "sleeper_league": "nba",
        "odds_api_markets": [
            "player_points",
            "player_rebounds",
        ],
        "odds_api_alternate_markets": [
            "player_points_alternate",
            "player_rebounds_alternate",
        ],
        "sleeper_stats": [
            "points",
            "pts_reb_ast",
            "points_and_rebounds",
            "points_and_assists",
            "rebounds_and_assists",
            "assists",
            "rebounds",
        ],
    },
    "NFL": {
        "sport_key": "americanfootball_nfl",
        "sleeper_league": "nfl",
        "odds_api_markets": ["player_pass_yds", "player_receptions"],
        "odds_api_alternate_markets": ["player_pass_yds_alternate", "player_receptions_alternate"],
        "sleeper_stats": [
            "passing_yards",
            "pass_completions",
            "rushing_yards",
            "receptions",
            "receiving_yards",
        ],
    },
    "NHL": {
        "sport_key": "icehockey_nhl",
        "sleeper_league": "nhl",
        "odds_api_markets": ["player_shots_on_goal", "player_points"],
        "odds_api_alternate_markets": ["player_shots_on_goal_alternate", "player_points_alternate"],
        "sleeper_stats": ["shots", "points", "saves"],
    },
    "MLB": {
        "sport_key": "baseball_mlb",
        "sleeper_league": "mlb",
        "odds_api_markets": ["pitcher_strikeouts", "batter_hits"],
        "odds_api_alternate_markets": ["pitcher_strikeouts_alternate", "batter_hits_alternate"],
        "sleeper_stats": ["strike_outs", "outs", "hits", "total_bases"],
    },
}


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def api_keys() -> list[str]:
    load_env()
    raw = os.environ.get("API_KEYS") or os.environ.get("API_KEY")
    if not raw:
        raise SystemExit("Set API_KEYS (or API_KEY) in .env for the-odds-api requests.")
    return [key.strip() for key in raw.split(",") if key.strip()]


def sleeper_auth() -> str | None:
    load_env()
    return os.environ.get("SLEEPER_AUTH")


def default_date_range(days_ahead: int = 3) -> tuple[date, date]:
    today = date.today()
    return today, today + timedelta(days=days_ahead)


def write_fixture(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {path} ({path.stat().st_size:,} bytes)")
