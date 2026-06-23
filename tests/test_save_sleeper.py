import json
from pathlib import Path

import pytest

from src.sleeper.saveSleeper import buildLegRows, checkResult, formatSheetRow, getPromoLeague, getStatName

PARLAYS_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "sleeper"
    / "graphql"
    / "my_parlays_completed.json"
)


@pytest.fixture
def completed_parlays():
    return json.loads(PARLAYS_FIXTURE.read_text())["data"]["my_parlays"]


def test_get_stat_name_mappings():
    assert getStatName("points") == "Pts"
    assert getStatName("pts_reb_ast") == "PRA"
    assert getStatName("unknown_stat") == "unknown_stat"


def test_get_promo_league_markers():
    assert getPromoLeague("over_boost") == "Over Boost"
    assert getPromoLeague("line_discount") == "Line Discount"
    assert getPromoLeague("something_new") == "Promo"
    assert getPromoLeague("") == "Promo"
    assert getPromoLeague(None) == "Promo"


def test_format_sheet_row_writes_wager_on_last_leg_only():
    leg = {"name": "A", "league": "NBA", "stat": "Pts", "payout": "1.5", "ou": "O", "result": "H"}
    assert formatSheetRow("06/05/25", leg) == ["06/05/25", "A", "NBA", "Pts", "1.5", "O", "H"]
    assert formatSheetRow("06/05/25", leg, profit=12.0, wager=10.0) == [
        "06/05/25", "A", "NBA", "Pts", "1.5", "O", "H", 12.0, 10.0,
    ]


def test_build_leg_rows_writes_promo_with_marker_league(completed_parlays):
    rows = buildLegRows(completed_parlays[0])
    # All three legs are kept: 2 PropRadar picks + 1 promo (none canceled here).
    assert [r["name"] for r in rows] == ["LeBron James", "Stephen Curry", "Anthony Davis"]

    promo = rows[-1]
    # The promo leg's league is the marker, not its real sport (NBA).
    assert promo["league"] == "Line Discount"
    assert promo["stat"] == "Reb"
    assert promo["payout"] == "1.40"
    assert promo["ou"] == "O"
    assert promo["result"] == "H"

    # The PropRadar picks keep their real sport.
    assert all(r["league"] == "NBA" for r in rows[:2])


def test_build_leg_rows_falls_back_to_parlay_promo_type():
    entry = {
        "display_data": {"promo_type": "over_boost"},
        "legs": [
            {
                "status": "won",
                "line": {
                    "subject": {"first_name": "Test", "last_name": "Player"},
                    "outcome": "over",
                    "sport": "nba",
                    "wager_type": "points",
                    "payout_multiplier": "1.80",
                    # promotion flagged, but no per-leg promotion_type.
                    "metadata": {"promotion": "true"},
                },
            }
        ],
    }
    rows = buildLegRows(entry)
    assert len(rows) == 1
    assert rows[0]["league"] == "Over Boost"


def test_build_leg_rows_skips_canceled_legs(completed_parlays):
    rows = buildLegRows(completed_parlays[1])
    # Second parlay has a canceled leg (Ja Morant) that must be dropped.
    assert [r["name"] for r in rows] == ["Kevin Durant"]


@pytest.mark.parametrize(
    "ou,line,score,expected",
    [
        ("O", 20.5, {"score": 20.5, "unders_win_dnp": False}, "P"),
        ("O", 20.5, {"score": 21, "unders_win_dnp": False}, "H"),
        ("U", 20.5, {"score": 20, "unders_win_dnp": False}, "H"),
    ],
)
def test_check_result(ou, line, score, expected):
    assert checkResult(ou, line, score) == expected
