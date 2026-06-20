from datetime import date

from src.prizePicks.gobbyFinder import parse_goblin_players
from src.prizePicks.pp import parse_standard_players

NBA_PP_STATS = ["Points", "Pts+Rebs+Asts", "Pts+Rebs", "Pts+Asts", "Rebounds", "Assists"]
FIXTURE_DATE = date(2026, 6, 13)


def test_parse_standard_players_from_fixture(nba_projections_fixture):
    players = parse_standard_players(
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
    players = parse_standard_players(
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
    odds_by_id = {
        item["id"]: item["attributes"]["odds_type"] for item in nba_projections_fixture["data"]
    }
    assert any(odds == "demon" for odds in odds_by_id.values())
    assert any("Combo" in item["attributes"]["stat_type"] for item in nba_projections_fixture["data"])

    standard = parse_standard_players(
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
