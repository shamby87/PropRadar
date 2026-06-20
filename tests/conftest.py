import json
import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# Required before src.utils is imported (module-level env reads and Discord clients).
os.environ.setdefault("API_KEYS", "test-key")
os.environ.setdefault("PARLAY_WEBHOOK", "https://example.com/parlay")
os.environ.setdefault("ADMIN_WEBHOOK", "https://example.com/admin")
os.environ.setdefault("SLEEPER_PLAYS_WEBHOOK", "https://example.com/plays")
os.environ.setdefault("ADMIN_ID", "1")
os.environ.setdefault("SLEEPER_ROLE_ID", "2")
os.environ.setdefault("SLEEPER_DRY_RUN", "1")


@pytest.fixture(autouse=True)
def reset_utils_state():
    import src.utils as utils

    utils._parsed_args = None
    for key in (
        "SPORT",
        "api_stats",
        "sleeper_stats",
        "pp_stats",
        "league",
        "offset",
        "start_day",
        "end_day",
    ):
        utils.__dict__.pop(key, None)

    class FakeArgs:
        league = None
        start_day = None
        end_day = None
        dry_run = True
        from_file = False
        live = False

    utils._parsed_args = FakeArgs()
    yield
    utils._parsed_args = None


@pytest.fixture
def fixture_json():
    def _load(name: str):
        return json.loads((FIXTURES_DIR / name).read_text())

    return _load


@pytest.fixture
def nba_projections_fixture(fixture_json):
    return fixture_json("prizepicks/nba_projections.json")


@pytest.fixture
def nba_sleeper_lines_fixture(fixture_json):
    return fixture_json("sleeper/nba_lines_available.json")


@pytest.fixture
def nba_sleeper_players_fixture(fixture_json):
    return fixture_json("sleeper/nba_players.json")


@pytest.fixture
def nba_odds_events_fixture(fixture_json):
    return fixture_json("odds_api/nba_events.json")


@pytest.fixture
def nba_odds_player_points_fixture(fixture_json):
    return fixture_json("odds_api/nba_player_points.json")

