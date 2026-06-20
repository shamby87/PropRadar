import json

import pytest

from src.sleeper import autoSleeper


def _sample_play(**overrides):
    base = {
        "name": "lebron james",
        "ou": "Over",
        "line": 25.5,
        "lineId": "line-1",
        "SleeperStat": "points",
        "payout": 1.5,
        "team": "LAL",
        "sport": "nba",
    }
    base.update(overrides)
    return base


def test_play_to_leg():
    leg = autoSleeper.play_to_leg(_sample_play())
    assert leg == {
        "player": "Lebron James",
        "stat": "points",
        "ou": "over",
        "line": 25.5,
        "payout": 1.5,
    }


def test_find_next_play_index_skips_same_team_sport():
    plays = [
        _sample_play(team="LAL", sport="nba"),
        _sample_play(team="LAL", sport="nba", lineId="line-2"),
        _sample_play(team="BOS", sport="nba", lineId="line-3"),
    ]
    assert autoSleeper.find_next_play_index(plays, "LAL", "nba") == 2


def test_find_next_play_index_returns_none_when_no_alternate_play():
    plays = [_sample_play(team="LAL", sport="nba")]
    assert autoSleeper.find_next_play_index(plays, "LAL", "nba") is None


def test_build_parlay_two_legs():
    first_leg = autoSleeper.play_to_leg(_sample_play())
    available = [
        _sample_play(team="LAL", sport="nba", lineId="skip"),
        _sample_play(team="BOS", sport="nba", lineId="line-2", payout=1.2, ou="Under"),
    ]
    line_ids, multiplier, parlay = autoSleeper.build_parlay(
        first_leg,
        "line-0",
        1.5,
        "LAL",
        "nba",
        available,
        num_extra_plays=1,
    )
    assert line_ids == ["line-0", "line-2"]
    assert multiplier == pytest.approx(1.8)
    assert len(parlay) == 2
    assert parlay[1]["ou"] == "under"


def test_promo_to_leg(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerName",
        lambda player_id, sport: "og anunoby",
    )
    promo = {
        "playerId": "1831",
        "sport": "nba",
        "stat": "points",
        "line": 18.5,
        "payout": 1.95,
    }
    assert autoSleeper.promo_to_leg(promo) == {
        "player": "Og Anunoby",
        "stat": "points",
        "ou": "over",
        "line": 18.5,
        "payout": 1.95,
    }


def test_find_next_play_index_empty_list():
    assert autoSleeper.find_next_play_index([], "LAL", "nba") is None


def test_build_parlay_three_legs():
    first_leg = autoSleeper.play_to_leg(_sample_play())
    available = [
        _sample_play(team="LAL", sport="nba", lineId="skip"),
        _sample_play(team="BOS", sport="nba", lineId="line-2", payout=1.2),
        _sample_play(team="MIA", sport="nba", lineId="line-3", payout=1.1),
    ]
    line_ids, multiplier, parlay = autoSleeper.build_parlay(
        first_leg,
        "line-0",
        1.5,
        "LAL",
        "nba",
        available,
        num_extra_plays=2,
    )
    assert line_ids == ["line-0", "line-2", "skip"]
    assert multiplier == pytest.approx(2.7)
    assert len(parlay) == 3


def _qualifying_play(**overrides):
    base = {
        "avgAdvantage": 1.1,
        "payout": 1.5,
        "playerId": "9999",
    }
    base.update(overrides)
    return _sample_play(**base)


def test_get_best_available_plays_filters_and_posts(monkeypatch):
    posted = []
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getParlays",
        lambda pending=False: [
            {
                "legs": [
                    {
                        "line": {
                            "metadata": {},
                            "subject_id": "1111",
                        }
                    }
                ]
            }
        ],
    )
    monkeypatch.setattr(
        autoSleeper.sleeper,
        "getBestPlays",
        lambda: {
            "good": _qualifying_play(),
            "weak": _qualifying_play(avgAdvantage=1.0, name="weak player"),
            "expensive": _qualifying_play(payout=3.0, name="expensive player"),
            "taken": _qualifying_play(playerId="1111", name="taken player"),
        },
    )
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "postPlaysToDiscord",
        lambda plays: posted.append(plays),
    )

    plays = autoSleeper.getBestAvailablePlays()
    assert len(plays) == 1
    assert plays[0]["name"] == "lebron james"
    assert len(posted) == 1


def test_get_best_available_plays_no_lines(monkeypatch, configure_utils):
    configure_utils()
    monkeypatch.setattr(autoSleeper.sleepUtils, "getParlays", lambda pending=False: [])
    monkeypatch.setattr(autoSleeper.sleeper, "getBestPlays", lambda: None)
    assert autoSleeper.getBestAvailablePlays() == []


def test_try_create_parlay_dry_run(capsys):
    parlay = [autoSleeper.play_to_leg(_sample_play())]
    assert autoSleeper.try_create_parlay(["line-1"], 1.5, 10, parlay, dry_run=True) is True
    assert "Overall Payout" in capsys.readouterr().out


def test_try_create_parlay_http_error(monkeypatch):
    class Resp:
        status_code = 500
        reason = "Error"
        content = b"fail"

    monkeypatch.setattr(autoSleeper.sleepUtils, "createParlay", lambda *args, **kwargs: Resp())
    parlay = [autoSleeper.play_to_leg(_sample_play())]
    assert autoSleeper.try_create_parlay(["line-1"], 1.5, 10, parlay) is False


def test_try_create_parlay_graphql_error(monkeypatch):
    from src.sleeper.sleepUtils import SleeperApiError

    class Resp:
        status_code = 200
        reason = "OK"
        content = b"{}"

    monkeypatch.setattr(autoSleeper.sleepUtils, "createParlay", lambda *args, **kwargs: Resp())
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "parse_graphql_data",
        lambda *args, **kwargs: (_ for _ in ()).throw(SleeperApiError("bad graphql")),
    )
    parlay = [autoSleeper.play_to_leg(_sample_play())]
    assert autoSleeper.try_create_parlay(["line-1"], 1.5, 10, parlay) is False


def test_try_create_parlay_null_response(monkeypatch):
    class Resp:
        status_code = 200
        reason = "OK"
        content = b'{"data":{"create_parlay":null}}'

    monkeypatch.setattr(autoSleeper.sleepUtils, "createParlay", lambda *args, **kwargs: Resp())
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "parse_graphql_data",
        lambda *args, **kwargs: {"create_parlay": None},
    )
    parlay = [autoSleeper.play_to_leg(_sample_play())]
    assert autoSleeper.try_create_parlay(["line-1"], 1.5, 10, parlay) is False


def test_try_create_parlay_success(monkeypatch, capsys):
    class Resp:
        status_code = 200
        reason = "OK"
        content = b'{"data":{"create_parlay":{"parlay_id":"pid-1"}}}'

    monkeypatch.setattr(autoSleeper.sleepUtils, "createParlay", lambda *args, **kwargs: Resp())
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "parse_graphql_data",
        lambda *args, **kwargs: {"create_parlay": {"parlay_id": "pid-1"}},
    )
    parlay = [autoSleeper.play_to_leg(_sample_play())]
    assert autoSleeper.try_create_parlay(["line-1"], 1.556, 10, parlay) is True
    assert "1.55x" in capsys.readouterr().out


def test_place_plays_aborts_without_promos(monkeypatch):
    monkeypatch.setattr(autoSleeper.sleepUtils, "getPlayerPromos", lambda: None)
    autoSleeper.placePlays(dry_run=True)


def test_place_plays_aborts_without_best_plays(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            }
        ],
    )
    monkeypatch.setattr(autoSleeper, "getBestAvailablePlays", lambda: [])
    autoSleeper.placePlays(dry_run=True)


def test_place_plays_aborts_without_balance(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            }
        ],
    )
    monkeypatch.setattr(autoSleeper, "getBestAvailablePlays", lambda: [_qualifying_play(team="BOS")])
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 0)
    autoSleeper.placePlays(dry_run=True)


def test_place_plays_dry_run_success(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        autoSleeper,
        "getBestAvailablePlays",
        lambda: [_qualifying_play(team="BOS", sport="nba", lineId="line-2")],
    )
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 25.0)
    monkeypatch.setattr(autoSleeper.sleepUtils, "getPlayerName", lambda pid, sport: "og anunoby")
    created = []
    monkeypatch.setattr(
        autoSleeper,
        "try_create_parlay",
        lambda *args, **kwargs: created.append(args) or True,
    )
    autoSleeper.placePlays(dry_run=True)
    assert len(created) == 1


def test_non_promo_plays_dry_run(monkeypatch):
    plays = [
        _qualifying_play(team="LAL", sport="nba", lineId="line-a"),
        _qualifying_play(team="BOS", sport="nba", lineId="line-b", name="jaylen brown"),
    ]
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 20.0)
    created = []
    monkeypatch.setattr(
        autoSleeper,
        "try_create_parlay",
        lambda *args, **kwargs: created.append(args) or True,
    )
    autoSleeper.nonPromoPlays(list(plays), dry_run=True)
    assert len(created) == 1


def test_non_promo_plays_no_funds(monkeypatch):
    monkeypatch.setattr(autoSleeper, "getBestAvailablePlays", lambda: [_qualifying_play(), _qualifying_play()])
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: None)
    autoSleeper.nonPromoPlays()


def test_place_plays_skips_incompatible_promo(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        autoSleeper,
        "getBestAvailablePlays",
        lambda: [_qualifying_play(team="NYK", sport="nba", lineId="line-2")],
    )
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 25.0)
    monkeypatch.setattr(autoSleeper.sleepUtils, "getPlayerName", lambda pid, sport: "og anunoby")
    created = []
    monkeypatch.setattr(
        autoSleeper,
        "try_create_parlay",
        lambda *args, **kwargs: created.append(args) or True,
    )
    autoSleeper.placePlays(dry_run=True)
    assert created == []


def test_get_best_available_plays_excludes_promo_legs_from_parlays(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getParlays",
        lambda pending=False: [
            {
                "legs": [
                    {
                        "line": {
                            "metadata": {"promotion": "true"},
                            "subject_id": "1111",
                        }
                    }
                ]
            }
        ],
    )
    monkeypatch.setattr(
        autoSleeper.sleeper,
        "getBestPlays",
        lambda: {"taken": _qualifying_play(playerId="1111", name="taken player")},
    )
    monkeypatch.setattr(autoSleeper.sleepUtils, "postPlaysToDiscord", lambda plays: None)
    plays = autoSleeper.getBestAvailablePlays()
    assert len(plays) == 1


def test_build_parlay_stops_when_out_of_plays_on_second_leg():
    first_leg = autoSleeper.play_to_leg(_sample_play())
    available = [_sample_play(team="LAL", sport="nba", lineId="skip")]
    line_ids, multiplier, parlay = autoSleeper.build_parlay(
        first_leg,
        "line-0",
        1.5,
        "LAL",
        "nba",
        available,
        num_extra_plays=2,
    )
    assert line_ids == ["line-0"]


def test_place_plays_filters_low_increase_promos(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.01,
            }
        ],
    )
    autoSleeper.placePlays(dry_run=True)


def test_place_plays_ran_out_of_funds(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            },
            {
                "playerId": "2146",
                "type": "line_discount",
                "sport": "nba",
                "team": "SAS",
                "stat": "points",
                "lineId": "promo-line-2",
                "line": 12.5,
                "payout": 1.9,
                "ogLine": 14.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            },
        ],
    )
    monkeypatch.setattr(
        autoSleeper,
        "getBestAvailablePlays",
        lambda: [
            _qualifying_play(team="BOS", sport="nba", lineId="line-2"),
            _qualifying_play(team="MIA", sport="nba", lineId="line-3", name="jimmy butler"),
        ],
    )
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 5.0)
    monkeypatch.setattr(autoSleeper.sleepUtils, "getPlayerName", lambda pid, sport: "player")
    monkeypatch.setattr(autoSleeper, "try_create_parlay", lambda *args, **kwargs: True)
    monkeypatch.setattr(autoSleeper, "sleep", lambda seconds: None)
    autoSleeper.placePlays(dry_run=False)


def test_non_promo_plays_breaks_on_single_leg(monkeypatch):
    plays = [_qualifying_play(team="LAL", sport="nba", lineId="line-a")]
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 20.0)
    autoSleeper.nonPromoPlays(plays, dry_run=True)
    assert len(plays) == 1


def test_place_plays_swaps_promo_when_no_compatible_play(monkeypatch):
    promos = [
        {
            "playerId": "1831",
            "type": "line_discount",
            "sport": "nba",
            "team": "NYK",
            "stat": "points",
            "lineId": "promo-line-1",
            "line": 18.5,
            "payout": 1.95,
            "ogLine": 20.5,
            "ogPayout": 1.8,
            "increase": 0.1,
        },
        {
            "playerId": "2146",
            "type": "line_discount",
            "sport": "nba",
            "team": "SAS",
            "stat": "points",
            "lineId": "promo-line-2",
            "line": 12.5,
            "payout": 1.9,
            "ogLine": 14.5,
            "ogPayout": 1.8,
            "increase": 0.1,
        },
    ]
    monkeypatch.setattr(autoSleeper.sleepUtils, "getPlayerPromos", lambda: list(promos))
    monkeypatch.setattr(
        autoSleeper,
        "getBestAvailablePlays",
        lambda: [_qualifying_play(team="NYK", sport="nba", lineId="line-2")],
    )
    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", lambda: 25.0)
    monkeypatch.setattr(autoSleeper.sleepUtils, "getPlayerName", lambda pid, sport: "player")
    created = []
    monkeypatch.setattr(
        autoSleeper,
        "try_create_parlay",
        lambda *args, **kwargs: created.append(args) or True,
    )
    autoSleeper.placePlays(dry_run=True)
    assert len(created) >= 1


def test_non_promo_plays_runs_out_of_funds(monkeypatch):
    plays = [
        _qualifying_play(team="LAL", sport="nba", lineId="line-a"),
        _qualifying_play(team="BOS", sport="nba", lineId="line-b", name="jaylen brown"),
        _qualifying_play(team="MIA", sport="nba", lineId="line-c", name="jimmy butler"),
    ]
    balances = iter([5.0, 0.0])

    def next_balance():
        return next(balances, 0.0)

    monkeypatch.setattr(autoSleeper.sleepUtils, "getBalance", next_balance)
    monkeypatch.setattr(autoSleeper, "try_create_parlay", lambda *args, **kwargs: True)
    monkeypatch.setattr(autoSleeper, "sleep", lambda seconds: None)
    autoSleeper.nonPromoPlays(plays, dry_run=False)


def test_place_plays_handles_get_best_available_exception(monkeypatch):
    monkeypatch.setattr(
        autoSleeper.sleepUtils,
        "getPlayerPromos",
        lambda: [
            {
                "playerId": "1831",
                "type": "line_discount",
                "sport": "nba",
                "team": "NYK",
                "stat": "points",
                "lineId": "promo-line",
                "line": 18.5,
                "payout": 1.95,
                "ogLine": 20.5,
                "ogPayout": 1.8,
                "increase": 0.1,
            }
        ],
    )

    def boom():
        raise RuntimeError("api down")

    monkeypatch.setattr(autoSleeper, "getBestAvailablePlays", boom)
    autoSleeper.placePlays(dry_run=True)


def test_non_promo_plays_exception_path(monkeypatch):
    monkeypatch.setattr(
        autoSleeper,
        "getBestAvailablePlays",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    autoSleeper.nonPromoPlays()

