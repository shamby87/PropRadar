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
    utils.API_KEY_INDEX = 0
    utils.API_KEYS = os.environ.get("API_KEYS", "test-key").split(",")
    utils.remainingRequests = 0
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


@pytest.fixture
def nba_odds_player_points_alternate_fixture(fixture_json):
    return fixture_json("odds_api/nba_player_points_alternate.json")


@pytest.fixture
def fake_nba_args():
    """CLI args that configure utils for NBA without interactive input."""

    class FakeArgs:
        league = "NBA"
        start_day = 0
        end_day = 3
        dry_run = True
        from_file = False
        live = False

    return FakeArgs()


@pytest.fixture
def configure_utils(monkeypatch, fake_nba_args):
    """Reset and call getArgs() with fake NBA CLI args."""
    import src.utils as utils

    def _configure(league=None, start_day=None, end_day=None, **kwargs):
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

        args = type(
            "FakeArgs",
            (),
            {
                "league": league if league is not None else fake_nba_args.league,
                "start_day": start_day if start_day is not None else fake_nba_args.start_day,
                "end_day": end_day if end_day is not None else fake_nba_args.end_day,
                "dry_run": kwargs.get("dry_run", fake_nba_args.dry_run),
                "from_file": kwargs.get("from_file", fake_nba_args.from_file),
                "live": kwargs.get("live", fake_nba_args.live),
            },
        )()
        monkeypatch.setattr(utils, "parse_args", lambda argv=None: args)
        utils.getArgs()
        return utils

    return _configure

