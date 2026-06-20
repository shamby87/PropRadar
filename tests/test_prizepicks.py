import json
from datetime import date
from unittest.mock import mock_open

import pytest

from src.prizePicks.gobbyFinder import parse_goblin_players
from src.prizePicks import pp

NBA_PP_STATS = ["Points", "Pts+Rebs+Asts", "Pts+Rebs", "Pts+Asts", "Rebounds", "Assists"]
FIXTURE_DATE = date(2026, 6, 13)


def test_parse_standard_players_from_fixture(nba_projections_fixture):
    players = pp.parse_standard_players(
        nba_projections_fixture,
        NBA_PP_STATS,
        league="NBA",
        start_day=FIXTURE_DATE,
        end_day=FIXTURE_DATE,
    )

    assert players["Points"]
    assert players["Pts+Rebs+Asts"]
    assert players["Rebounds"]
    assert players["Assists"]

    assert "victor wembanyama" in players["Points"]
    assert players["Points"]["victor wembanyama"]["PPLine"] == 28.5
    assert players["Points"]["victor wembanyama"]["avgDif"] == 0


def test_parse_standard_players_use_standard_lines_not_goblin(nba_projections_fixture):
    players = pp.parse_standard_players(
        nba_projections_fixture,
        ["Pts+Rebs+Asts"],
        league="NBA",
        start_day=FIXTURE_DATE,
        end_day=FIXTURE_DATE,
    )

    assert "victor wembanyama" in players["Pts+Rebs+Asts"]
    assert players["Pts+Rebs+Asts"]["victor wembanyama"]["PPLine"] == 43.5


def test_parse_goblin_players_from_fixture(nba_projections_fixture):
    players = parse_goblin_players(
        nba_projections_fixture,
        NBA_PP_STATS,
        league="NBA",
        start_day=FIXTURE_DATE,
        end_day=FIXTURE_DATE,
    )

    assert players["Points"]
    assert players["Pts+Rebs+Asts"]
    assert "victor wembanyama" in players["Pts+Rebs+Asts"]
    assert players["Pts+Rebs+Asts"]["victor wembanyama"]["PPLine"] == 40.5


def test_parse_goblin_players_ignores_standard_rows(nba_projections_fixture):
    players = parse_goblin_players(
        nba_projections_fixture,
        ["Points"],
        league="NBA",
        start_day=FIXTURE_DATE,
        end_day=FIXTURE_DATE,
    )

    # Standard Victor Wembanyama Points line is 28.5 and must not appear as goblin output.
    assert "victor wembanyama" not in players["Points"]
    assert players["Points"]["jalen brunson"]["PPLine"] == 26.5


def test_fixture_demon_and_combo_rows(nba_projections_fixture):
    standard = pp.parse_standard_players(
        nba_projections_fixture,
        ["Pts+Rebs", "Points (Combo)"],
        league="NBA",
        start_day=FIXTURE_DATE,
        end_day=FIXTURE_DATE,
    )
    goblin = parse_goblin_players(
        nba_projections_fixture,
        ["Pts+Rebs"],
        league="NBA",
        start_day=FIXTURE_DATE,
        end_day=FIXTURE_DATE,
    )

    assert "victor wembanyama" in standard["Pts+Rebs"]
    assert standard["Pts+Rebs"]["victor wembanyama"]["PPLine"] == 40.5
    assert "victor wembanyama + jalen brunson" in standard["Points (Combo)"]

    assert goblin["Pts+Rebs"]["victor wembanyama"]["PPLine"] == 34.5

    demon_lines = {
        item["attributes"]["line_score"]
        for item in nba_projections_fixture["data"]
        if item["attributes"]["odds_type"] == "demon"
    }
    assert 54.5 in demon_lines
    assert standard["Pts+Rebs"]["victor wembanyama"]["PPLine"] not in demon_lines


def test_parse_standard_players_filters_by_date(nba_projections_fixture):
    players = pp.parse_standard_players(
        nba_projections_fixture,
        ["Points"],
        league="NBA",
        start_day=date(2099, 1, 1),
        end_day=date(2099, 1, 2),
    )
    assert players["Points"] == {}


def test_prizepicks_cookie_missing(monkeypatch):
    monkeypatch.delenv("PRIZEPICKS_COOKIE", raising=False)
    with pytest.raises(SystemExit, match="PRIZEPICKS_COOKIE"):
        pp.prizepicks_cookie()


def test_main_from_file(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
    nba_odds_events_fixture,
    nba_odds_player_points_fixture,
    capsys,
):
    utils = configure_utils(from_file=True, start_day=-10, end_day=0)
    raw = json.dumps(nba_projections_fixture)
    monkeypatch.setattr("builtins.open", mock_open(read_data=raw))
    event_ids = [event["id"] for event in nba_odds_events_fixture["events"]]
    odds_event = nba_odds_player_points_fixture["event"]
    monkeypatch.setattr(utils, "getEvents", lambda: event_ids)
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: odds_event if market == "player_points" else None,
    )

    pp.main()
    captured = capsys.readouterr()
    assert "Points:" in captured.out
    assert "Full best play:" in captured.out


def test_main_api_fetch_success(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
    nba_odds_events_fixture,
    nba_odds_player_points_fixture,
    capsys,
):
    utils = configure_utils(from_file=False, start_day=-10, end_day=0)
    monkeypatch.setenv("PRIZEPICKS_COOKIE", "session=abc")
    event_ids = [event["id"] for event in nba_odds_events_fixture["events"]]
    odds_event = nba_odds_player_points_fixture["event"]
    monkeypatch.setattr(utils, "getEvents", lambda: event_ids)
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: odds_event if market == "player_points" else None,
    )

    class FakeResp:
        status_code = 200
        content = json.dumps(nba_projections_fixture)
        reason = "OK"

    monkeypatch.setattr(pp.requests, "get", lambda url, headers: FakeResp())

    pp.main()
    assert "200" in capsys.readouterr().out


def test_main_api_fetch_failure_exits(
    monkeypatch,
    configure_utils,
):
    configure_utils(from_file=False)
    monkeypatch.setenv("PRIZEPICKS_COOKIE", "session=abc")

    class FakeResp:
        status_code = 403
        content = b"forbidden"
        reason = "Forbidden"

    monkeypatch.setattr(pp.requests, "get", lambda url, headers: FakeResp())

    with pytest.raises(SystemExit):
        pp.main()


def test_main_mlb_zero_threshold(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
    capsys,
):
    configure_utils(league="MLB", from_file=True)
    monkeypatch.setattr("builtins.open", mock_open(read_data=json.dumps(nba_projections_fixture)))
    monkeypatch.setattr("src.utils.getEvents", lambda: [])
    assert pp.THRESHOLD == 0.6
    pp.main()
    assert pp.THRESHOLD == 0
    pp.THRESHOLD = 0.6


def test_main_skips_mismatched_book_outcomes(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
    capsys,
):
    utils = configure_utils(from_file=True, start_day=-10, end_day=0)
    monkeypatch.setattr("builtins.open", mock_open(read_data=json.dumps(nba_projections_fixture)))
    monkeypatch.setattr(utils, "getEvents", lambda: ["evt-1"])
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: {
            "bookmakers": [
                {
                    "markets": [
                        {
                            "outcomes": [
                                {
                                    "name": "Over",
                                    "description": "Victor Wembanyama",
                                    "price": 1.9,
                                    "point": 28.5,
                                },
                                {
                                    "name": "Over",
                                    "description": "Victor Wembanyama",
                                    "price": 1.8,
                                    "point": 28.5,
                                },
                            ]
                        }
                    ]
                }
            ]
        },
    )
    pp.main()
    assert "Points:" in capsys.readouterr().out


def test_main_under_outcome_branch(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
):
    utils = configure_utils(from_file=True, start_day=-10, end_day=0)
    monkeypatch.setattr("builtins.open", mock_open(read_data=json.dumps(nba_projections_fixture)))
    monkeypatch.setattr(utils, "getEvents", lambda: ["evt-1"])
    book = {
        "markets": [
            {
                "outcomes": [
                    {
                        "name": "Under",
                        "description": "Victor Wembanyama",
                        "price": 1.82,
                        "point": 28.5,
                    },
                    {
                        "name": "Over",
                        "description": "Victor Wembanyama",
                        "price": 1.96,
                        "point": 28.5,
                    },
                    {
                        "name": "Under",
                        "description": "Jalen Brunson",
                        "price": 1.8,
                        "point": 26.5,
                    },
                    {
                        "name": "Over",
                        "description": "Jalen Brunson",
                        "price": 1.95,
                        "point": 26.5,
                    },
                    {
                        "name": "Under",
                        "description": "Josh Hart",
                        "price": 1.83,
                        "point": 9.5,
                    },
                    {
                        "name": "Over",
                        "description": "Josh Hart",
                        "price": 1.9,
                        "point": 9.5,
                    },
                ]
            }
        ]
    }
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: {"bookmakers": [book, book, book]},
    )
    pp.main()


def test_main_skips_unbalanced_book_markets(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
):
    utils = configure_utils(from_file=True, start_day=-10, end_day=0)
    monkeypatch.setattr("builtins.open", mock_open(read_data=json.dumps(nba_projections_fixture)))
    monkeypatch.setattr(utils, "getEvents", lambda: ["evt-1"])
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: {
            "bookmakers": [
                {
                    "markets": [
                        {
                            "outcomes": [
                                {
                                    "name": "Over",
                                    "description": "Victor Wembanyama",
                                    "price": 1.9,
                                    "point": 28.5,
                                },
                                {
                                    "name": "Under",
                                    "description": "Victor Wembanyama",
                                    "price": 1.8,
                                    "point": 28.5,
                                },
                                {
                                    "name": "Over",
                                    "description": "Jalen Brunson",
                                    "price": 1.9,
                                    "point": 26.5,
                                },
                            ]
                        }
                    ]
                }
            ]
        },
    )
    pp.main()


def test_main_stops_printing_low_edge_plays(
    monkeypatch,
    configure_utils,
    nba_projections_fixture,
):
    utils = configure_utils(from_file=True, start_day=-10, end_day=0)
    monkeypatch.setattr("builtins.open", mock_open(read_data=json.dumps(nba_projections_fixture)))
    monkeypatch.setattr(utils, "getEvents", lambda: ["evt-1"])
    book = {
        "markets": [
            {
                "outcomes": [
                    {
                        "name": "Over",
                        "description": "Victor Wembanyama",
                        "price": 1.91,
                        "point": 28.5,
                    },
                    {
                        "name": "Under",
                        "description": "Victor Wembanyama",
                        "price": 1.91,
                        "point": 28.5,
                    },
                ]
            }
        ]
    }
    monkeypatch.setattr(
        utils,
        "getEvent",
        lambda event_id, market: {"bookmakers": [book, book, book]},
    )
    pp.THRESHOLD = 5
    try:
        pp.main()
    finally:
        pp.THRESHOLD = 0.6

