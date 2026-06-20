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


def test_format_parlay_message():
    parlay = [
        {"player": "Lebron James", "ou": "over", "line": 25.5, "stat": "points", "payout": 1.5},
    ]
    msg = autoSleeper.format_parlay_message(parlay, 1.5, "abc123")
    assert "Lebron James" in msg
    assert "Overall Payout: **1.5x**" in msg
    assert "https://e.slpr.link/abc123" in msg
