import json

import pytest

from src.utils import ConfigError, OddsApiError, getRemainingRequests, logMsg, parse_args
from tests.helpers import FakeHttpResponse


@pytest.mark.parametrize(
    "league",
    [
        "NFL",
        "WNBA",
        "CBB",
        "NHL",
        "pass yards",
        "completions",
        "rush yards",
        "receptions",
        "rec yards",
        "NBA points",
        "NBA assists",
        "NBA rebounds",
        "strikeouts",
        "SOG",
    ],
)
def test_get_args_supported_leagues(monkeypatch, league):
    import src.utils as utils

    args = type(
        "FakeArgs",
        (),
        {
            "league": league,
            "start_day": 0,
            "end_day": 1,
            "dry_run": True,
            "from_file": False,
            "live": False,
        },
    )()
    monkeypatch.setattr(utils, "parse_args", lambda argv=None: args)
    utils.getArgs()
    assert utils.league is not None
    assert utils.SPORT
    assert utils.start_day <= utils.end_day


def test_parse_args_league_and_day_range():
    args = parse_args(["NBA", "0", "1"])
    assert args.league == "NBA"
    assert args.start_day == 0
    assert args.end_day == 1


def test_parse_args_dry_run_flag():
    args = parse_args(["NBA", "0", "1", "--dry-run"])
    assert args.dry_run is True


def test_parse_args_dry_run_from_env(monkeypatch):
    monkeypatch.setenv("SLEEPER_DRY_RUN", "true")
    args = parse_args(["NBA", "0", "1"])
    assert args.dry_run is True


def test_get_args_unknown_league(monkeypatch):
    import src.utils as utils

    class FakeArgs:
        league = "NOPE"
        start_day = 0
        end_day = 0
        dry_run = True
        from_file = False
        live = False

    monkeypatch.setattr(utils, "parse_args", lambda argv=None: FakeArgs())

    with pytest.raises(ConfigError, match="Unknown league/stat"):
        utils.getArgs()


def test_get_events_success(monkeypatch, configure_utils, nba_odds_events_fixture):
    utils = configure_utils(start_day=-10, end_day=0)
    events_payload = nba_odds_events_fixture["events"]

    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(
            json_data=events_payload,
            headers={"x-requests-remaining": "42"},
        ),
    )

    event_ids = utils.getEvents()
    assert event_ids == [events_payload[0]["id"]]


def test_get_events_out_of_usage_credits_rotates_key(monkeypatch, configure_utils, fixture_json):
    utils = configure_utils()
    utils.API_KEYS = ["key-a", "key-b"]
    utils.API_KEY_INDEX = 0
    calls = []

    def fake_get(url, params):
        calls.append(params["api_key"])
        if params["api_key"] == "key-a":
            return FakeHttpResponse(
                status_code=401,
                json_data=fixture_json("odds_api/out_of_usage_credits.json"),
            )
        return FakeHttpResponse(
            json_data=[],
            headers={"x-requests-remaining": "10"},
        )

    monkeypatch.setattr(utils.requests, "get", fake_get)
    assert utils.getEvents() == []
    assert calls == ["key-a", "key-b"]


def test_get_events_out_of_usage_credits_raises(monkeypatch, configure_utils, fixture_json):
    utils = configure_utils()
    utils.API_KEYS = ["only-key"]
    utils.API_KEY_INDEX = 0

    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(
            status_code=401,
            json_data=fixture_json("odds_api/out_of_usage_credits.json"),
        ),
    )

    with pytest.raises(OddsApiError, match="Out of API keys"):
        utils.getEvents()


def test_get_events_http_error(monkeypatch, configure_utils):
    utils = configure_utils()
    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(status_code=500, json_data={"error": "boom"}),
    )

    with pytest.raises(OddsApiError, match="Failed to get events"):
        utils.getEvents()


def test_get_event_success(monkeypatch, configure_utils, nba_odds_player_points_fixture):
    utils = configure_utils()
    event = nba_odds_player_points_fixture["event"]

    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(
            json_data=event,
            headers={"x-requests-remaining": "99", "x-requests-used": "1"},
        ),
    )

    result = utils.getEvent("evt-1", "player_points")
    assert result["id"] == event["id"]
    assert utils.remainingRequests == 99


def test_get_event_rate_limited_then_success(monkeypatch, configure_utils, nba_odds_player_points_fixture):
    utils = configure_utils()
    event = nba_odds_player_points_fixture["event"]
    calls = {"count": 0}

    def fake_get(url, params):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeHttpResponse(status_code=429, json_data={"error": "rate limit"})
        return FakeHttpResponse(
            json_data=event,
            headers={"x-requests-remaining": "50", "x-requests-used": "50"},
        )

    slept = []
    monkeypatch.setattr(utils.requests, "get", fake_get)
    monkeypatch.setattr(utils, "sleep", lambda seconds: slept.append(seconds))

    result = utils.getEvent("evt-1", "player_points")
    assert result["id"] == event["id"]
    assert slept == [utils.RATE_LIMIT_SLEEP]


def test_get_event_out_of_usage_credits(monkeypatch, configure_utils, fixture_json, nba_odds_player_points_fixture):
    utils = configure_utils()
    utils.API_KEYS = ["key-a", "key-b"]
    utils.API_KEY_INDEX = 0
    event = nba_odds_player_points_fixture["event"]
    calls = []

    def fake_get(url, params):
        calls.append(params["api_key"])
        if params["api_key"] == "key-a":
            return FakeHttpResponse(
                status_code=401,
                json_data=fixture_json("odds_api/out_of_usage_credits.json"),
            )
        return FakeHttpResponse(
            json_data=event,
            headers={"x-requests-remaining": "25", "x-requests-used": "75"},
        )

    monkeypatch.setattr(utils.requests, "get", fake_get)
    result = utils.getEvent("evt-1", "player_points")
    assert result["id"] == event["id"]
    assert calls[0] == "key-a"
    assert calls[1] == "key-b"


def test_get_event_other_error_returns_none(monkeypatch, configure_utils):
    utils = configure_utils()
    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(status_code=404, json_data={"error": "missing"}),
    )
    assert utils.getEvent("evt-1", "player_points") is None


def test_log_msg_dry_run_skips_discord(monkeypatch, configure_utils, capsys):
    utils = configure_utils(dry_run=True)
    posted = {"parlay": 0, "admin": 0, "plays": 0}
    monkeypatch.setattr(utils.PARLAY_CHANNEL, "post", lambda **kwargs: posted.__setitem__("parlay", 1))
    monkeypatch.setattr(utils.ADMIN_CHANNEL, "post", lambda **kwargs: posted.__setitem__("admin", 1))
    monkeypatch.setattr(utils.SLEEPER_PLAYS_CHANNEL, "post", lambda **kwargs: posted.__setitem__("plays", 1))

    logMsg("hello", sleeper=True, debug=True, sleepPlays=True)
    assert "hello" in capsys.readouterr().out
    assert posted == {"parlay": 0, "admin": 0, "plays": 0}


def test_log_msg_posts_when_not_dry_run(monkeypatch, configure_utils, capsys):
    utils = configure_utils(dry_run=False)
    posted = {"parlay": 0, "admin": 0, "plays": 0}
    monkeypatch.setattr(utils.PARLAY_CHANNEL, "post", lambda **kwargs: posted.__setitem__("parlay", 1))
    monkeypatch.setattr(utils.ADMIN_CHANNEL, "post", lambda **kwargs: posted.__setitem__("admin", 1))
    monkeypatch.setattr(utils.SLEEPER_PLAYS_CHANNEL, "post", lambda **kwargs: posted.__setitem__("plays", 1))

    logMsg("notify", sleeper=True, debug=True, sleepPlays=True, notify=False)
    assert posted == {"parlay": 1, "admin": 1, "plays": 1}


def test_parse_args_returns_cached_when_called_twice(monkeypatch):
    import sys

    import src.utils as utils

    utils._parsed_args = None
    monkeypatch.setattr(sys, "argv", ["prop_radar", "NBA", "0", "1"])
    first = parse_args()
    second = parse_args()
    assert first is second


def test_get_args_uses_interactive_league(monkeypatch):
    import src.utils as utils

    class FakeArgs:
        league = None
        start_day = 0
        end_day = 0
        dry_run = True
        from_file = False
        live = False

    monkeypatch.setattr(utils, "parse_args", lambda argv=None: FakeArgs())
    monkeypatch.setattr("builtins.input", lambda prompt: "NBA")
    utils.getArgs()
    assert utils.league == "NBA"


def test_get_args_uses_interactive_day_range(monkeypatch):
    import src.utils as utils

    class FakeArgs:
        league = "NBA"
        start_day = None
        end_day = None
        dry_run = True
        from_file = False
        live = False

    inputs = iter(["0", "2"])
    monkeypatch.setattr(utils, "parse_args", lambda argv=None: FakeArgs())
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    utils.getArgs()
    assert utils.start_day <= utils.end_day


def test_get_event_out_of_usage_credits_exhausted(monkeypatch, configure_utils, fixture_json):
    utils = configure_utils()
    utils.API_KEYS = ["only-key"]
    utils.API_KEY_INDEX = 0

    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(
            status_code=401,
            json_data=fixture_json("odds_api/out_of_usage_credits.json"),
        ),
    )

    with pytest.raises(OddsApiError, match="Out of API keys"):
        utils.getEvent("evt-1", "player_points")


def test_get_events_invalid_json_response(monkeypatch, configure_utils):
    utils = configure_utils()

    monkeypatch.setattr(
        utils.requests,
        "get",
        lambda url, params: FakeHttpResponse(status_code=500, content=b"not-json"),
    )

    with pytest.raises(OddsApiError, match="Failed to get events"):
        utils.getEvents()


def test_get_remaining_requests():
    import src.utils as utils

    utils.API_KEY_INDEX = 0
    utils.API_KEYS = ["k1", "k2", "k3"]
    utils.remainingRequests = 120
    assert getRemainingRequests() == 120 + 2 * 500
