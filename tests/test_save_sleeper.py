import pytest

from src.sleeper.saveSleeper import checkResult, getStatName


def test_get_stat_name_mappings():
    assert getStatName("points") == "Pts"
    assert getStatName("pts_reb_ast") == "PRA"
    assert getStatName("unknown_stat") == "unknown_stat"


@pytest.mark.parametrize(
    "ou,line,score,expected",
    [
        ("O", 20.5, {"score": 20.5, "unders_win_dnp": False}, "P"),
        ("O", 20.5, {"score": 21, "unders_win_dnp": False}, "H"),
        ("O", 20.5, {"score": 20, "unders_win_dnp": False}, "M"),
        ("U", 20.5, {"score": 20, "unders_win_dnp": False}, "H"),
        ("U", 20.5, {"score": 21, "unders_win_dnp": False}, "M"),
        ("U", 20.5, {"score": 25, "unders_win_dnp": True}, "H"),
    ],
)
def test_check_result(ou, line, score, expected):
    assert checkResult(ou, line, score) == expected
