import pytest

from src.prizePicks.savePP import formatSheetRow


def test_format_sheet_row_writes_wager_on_last_leg_only():
    leg = {"name": "A", "league": "NBA", "stat": "Pts", "ou": "O", "result": "H"}
    assert formatSheetRow("06/05/25", leg) == ["06/05/25", "A", "NBA", "Pts", "", "O", "H"]
    assert formatSheetRow("06/05/25", leg, profit=12.0, wager=10.0) == [
        "06/05/25", "A", "NBA", "Pts", "", "O", "H", 12.0, 10.0,
    ]


def test_format_sheet_row_allows_zero_profit_push():
    leg = {"name": "A", "league": "NBA", "stat": "Pts", "ou": "O", "result": "P"}
    assert formatSheetRow("06/05/25", leg, profit=0.0, wager=5.0) == [
        "06/05/25", "A", "NBA", "Pts", "", "O", "P", 0.0, 5.0,
    ]
