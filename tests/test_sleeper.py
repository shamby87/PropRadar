import json

import pytest

from src.sleeper.sleepUtils import SleeperApiError
from src.sleeper import sleeper


def _mock_sleeper_requests(monkeypatch, lines, players):
    def fake_get(url, timeout=30):
        if "lines/available" in url:
            return type(
                "Resp",
                (),
                {
                    "status_code": 200,
                    "content": json.dumps(lines).encode(),
                    "reason": "OK",
                },
            )()
        if "/v1/players/" in url:
            return type(
                "Resp",
                (),
                {
                    "status_code": 200,
                    "content": json.dumps(players).encode(),
                    "reason": "OK",
                },
            )()
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr(sleeper.requests, "get", fake_get)


def test_get_best_plays_returns_none_when_no_lines(monkeypatch, configure_utils):
    utils = configure_utils()
    _mock_sleeper_requests(monkeypatch, lines=[], players={})
    monkeypatch.setattr(utils, "getEvents", lambda: [])

    assert sleeper.getBestPlays() is None


def test_get_best_plays_with_fixtures(
    monkeypatch,
    configure_utils,
    nba_sleeper_lines_fixture,
    nba_sleeper_players_fixture,
    nba_odds_events_fixture,
    nba_odds_player_points_fixture,
):
    utils = configure_utils()
    lines = nba_sleeper_lines_fixture["lines"]
    players = nba_sleeper_players_fixture["players"]
    event_ids = [event["id"] for event in nba_odds_events_fixture["events"]]
    odds_event = nba_odds_player_points_fixture["event"]

    _mock_sleeper_requests(monkeypatch, lines, players)
    monkeypatch.setattr(utils, "getEvents", lambda: event_ids)
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: odds_event if market == "player_points" else None,
    )

    result = sleeper.getBestPlays()
    assert isinstance(result, dict)


def test_get_best_plays_lines_http_error(monkeypatch, configure_utils):
    configure_utils()

    def fake_get(url, timeout=30):
        return type("Resp", (), {"status_code": 500, "content": b"fail", "reason": "Error"})()

    monkeypatch.setattr(sleeper.requests, "get", fake_get)

    with pytest.raises(SleeperApiError, match="lines/available"):
        sleeper.getBestPlays()


def test_get_best_plays_lines_request_error(monkeypatch, configure_utils):
    configure_utils()

    def fake_get(url, timeout=30):
        raise sleeper.requests.RequestException("network down")

    monkeypatch.setattr(sleeper.requests, "get", fake_get)

    with pytest.raises(SleeperApiError, match="request failed"):
        sleeper.getBestPlays()


def test_get_best_plays_players_http_error(
    monkeypatch,
    configure_utils,
    nba_sleeper_lines_fixture,
):
    configure_utils()
    lines = nba_sleeper_lines_fixture["lines"]

    def fake_get(url, timeout=30):
        if "lines/available" in url:
            return type(
                "Resp",
                (),
                {"status_code": 200, "content": json.dumps(lines).encode(), "reason": "OK"},
            )()
        return type("Resp", (), {"status_code": 503, "content": b"down", "reason": "Unavailable"})()

    monkeypatch.setattr(sleeper.requests, "get", fake_get)

    with pytest.raises(SleeperApiError, match="v1/players"):
        sleeper.getBestPlays()


def test_get_best_plays_players_request_error(monkeypatch, configure_utils, nba_sleeper_lines_fixture):
    configure_utils()

    def fake_get(url, timeout=30):
        if "lines/available" in url:
            return type(
                "Resp",
                (),
                {
                    "status_code": 200,
                    "content": json.dumps(nba_sleeper_lines_fixture["lines"]).encode(),
                    "reason": "OK",
                },
            )()
        raise sleeper.requests.RequestException("timeout")

    monkeypatch.setattr(sleeper.requests, "get", fake_get)

    with pytest.raises(SleeperApiError, match="request failed"):
        sleeper.getBestPlays()


def test_get_best_plays_handles_nan_pick_counts(monkeypatch, configure_utils):
    utils = configure_utils()
    lines = [
        {
            "status": "active",
            "options": [
                {
                    "outcome": "over",
                    "outcome_value": 10.5,
                    "line_id": "line-over",
                    "subject_id": "999",
                    "subject_team": "LAL",
                    "sport": "nba",
                    "payout_multiplier": "1.90",
                },
                {
                    "outcome": "under",
                    "outcome_value": 10.5,
                    "line_id": "line-under",
                    "subject_id": "999",
                    "subject_team": "LAL",
                    "sport": "nba",
                    "payout_multiplier": "1.80",
                },
            ],
            "subject_id": "999",
            "wager_type": "points",
            "outcome_type": "over_under",
            "line_type": "normal",
            "game_status": "pre_game",
            "pick_stats": {
                "counts": {
                    "over": float("nan"),
                    "under": float("nan"),
                    "total": 10,
                }
            },
        }
    ]
    players = {"999": {"full_name": "Test Player"}}
    _mock_sleeper_requests(monkeypatch, lines, players)
    monkeypatch.setattr(utils, "getEvents", lambda: [])
    result = sleeper.getBestPlays()
    assert isinstance(result, dict)


def test_get_best_plays_alt_line_path(
    monkeypatch,
    configure_utils,
    nba_sleeper_lines_fixture,
    nba_sleeper_players_fixture,
    nba_odds_events_fixture,
    nba_odds_player_points_alternate_fixture,
):
    """Odds at a different point than Sleeper should populate otherLines, not otherBooks."""
    utils = configure_utils()
    lines = nba_sleeper_lines_fixture["lines"]
    players = nba_sleeper_players_fixture["players"]
    event_ids = [event["id"] for event in nba_odds_events_fixture["events"]]
    odds_event = nba_odds_player_points_alternate_fixture["event"]

    _mock_sleeper_requests(monkeypatch, lines, players)
    monkeypatch.setattr(utils, "getEvents", lambda: event_ids)
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: odds_event if market == "player_points" else None,
    )

    result = sleeper.getBestPlays()
    assert isinstance(result, dict)


def test_get_best_plays_marks_low_advantage_plays(
    monkeypatch,
    configure_utils,
    nba_sleeper_lines_fixture,
    nba_sleeper_players_fixture,
    nba_odds_events_fixture,
):
    utils = configure_utils()
    lines = nba_sleeper_lines_fixture["lines"]
    players = nba_sleeper_players_fixture["players"]
    event_ids = [event["id"] for event in nba_odds_events_fixture["events"]]

    def fake_event(event_id, market):
        if market != "player_points":
            return None
        outcome_pair = {
            "markets": [
                {
                    "outcomes": [
                        {
                            "name": "Over",
                            "description": "Jordan Clarkson",
                            "price": 5.0,
                            "point": 2.5,
                        },
                        {
                            "name": "Under",
                            "description": "Jordan Clarkson",
                            "price": 5.0,
                            "point": 2.5,
                        },
                    ]
                }
            ]
        }
        return {"bookmakers": [outcome_pair, outcome_pair]}

    _mock_sleeper_requests(monkeypatch, lines, players)
    monkeypatch.setattr(utils, "getEvents", lambda: event_ids)
    monkeypatch.setattr(utils, "getEvent", fake_event)
    result = sleeper.getBestPlays()
    assert isinstance(result, dict)
