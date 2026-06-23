import json
from datetime import date
from pathlib import Path

import pytest

from src.dashboard import stats
from src.dashboard.sheet_reader import Leg, ParlayEntry, apply_assumed_sleeper_promos, parse_rows

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dashboard" / "sample_sheet_rows.json"


@pytest.fixture
def sample_rows():
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def sample_entries(sample_rows):
    return parse_rows(sample_rows, "sleeper")


# ---- parse_rows ----

def test_parse_groups_legs_into_entries(sample_entries):
    # Header, blank separators, and the misc "Random" row are all skipped.
    assert len(sample_entries) == 3
    assert [len(e.legs) for e in sample_entries] == [2, 3, 2]


def test_parse_outcomes_and_dates(sample_entries):
    win, loss, push = sample_entries
    assert (win.outcome, win.profit, win.date) == ("win", 15.0, date(2025, 6, 1))
    assert (loss.outcome, loss.profit) == ("loss", -10.0)
    assert push.outcome == "push" and push.profit == 0.0


def test_parse_reads_optional_wager_column(sample_entries):
    assert [e.wager for e in sample_entries] == [10.0, 10.0, 8.0]


def test_parse_skips_malformed_profit():
    rows = [
        ["", "06/05/25", "Player A", "NBA", "Pts", "1.5", "O", "H", "", ""],
        ["", "06/05/25", "Player B", "NBA", "Pts", "1.5", "O", "H", "oops", ""],
    ]
    assert parse_rows(rows, "sleeper") == []


def test_parse_four_digit_year_and_sleeper_style_grouping():
    rows = [
        ["", "Date", "Name", "League", "Stat", "Payout", "O/U", "Hit/Miss", "Profit/Loss"],
        ["", "4/17/2024", "Jimmy Butler", "NBA", "Reb", "1.77", "O", "M", ""],
        ["", "4/17/2024", "Bam Adebayo", "NBA", "PRA", "1.90", "O", "M", "-$10.00"],
        [""],
        ["", "4/20/2024", "Max Strus", "NBA", "Ast", "1.85", "U", "H", ""],
        ["", "4/20/2024", "I Hartenstein", "NBA", "PRA", "2.17", "U", "H", "$30.50"],
    ]
    entries = parse_rows(rows, "sleeper")
    assert len(entries) == 2
    assert len(entries[0].legs) == 2
    assert entries[0].profit == -10.0
    assert entries[0].date == date(2024, 4, 17)
    assert entries[1].profit == 30.5


def test_parse_routes_promo_marker_legs_into_promo_legs():
    rows = [
        ["", "06/05/25", "Player A", "NBA", "Pts", "1.5", "O", "H", ""],
        ["", "06/05/25", "Promo Guy", "Line Discount", "Reb", "1.4", "O", "H", "$12.00"],
    ]
    entries = parse_rows(rows, "sleeper")
    assert len(entries) == 1
    entry = entries[0]
    # PropRadar pick stays in legs; the promo marker leg is routed to promo_legs.
    assert [leg.name for leg in entry.legs] == ["Player A"]
    assert [leg.name for leg in entry.promo_legs] == ["Promo Guy"]
    assert entry.promo_legs[0].is_promo is True
    assert entry.legs[0].is_promo is False
    assert entry.total_legs == 2


def test_promo_marker_excluded_from_skill_stats_but_counts_avg_legs():
    rows = [
        ["", "06/05/25", "Player A", "NBA", "Pts", "2.0", "O", "H", ""],
        # A juicy Over Boost promo that would wreck Est. Edge if it were counted.
        ["", "06/05/25", "Promo Guy", "Over Boost", "Reb", "9.0", "O", "H", "$12.00"],
    ]
    entries = parse_rows(rows, "sleeper")
    totals = stats.compute_platform_stats(entries)["totals"]
    assert totals["legs"] == 1  # promo excluded from PropRadar leg count
    assert totals["leg_hits"] == 1
    assert totals["avg_legs_per_parlay"] == pytest.approx(2.0)  # promo still counts
    # Only the 2.0 PropRadar pick feeds Est. Edge: 2.0 / 1 - 1 = +100%.
    assert totals["avg_ev"] == pytest.approx(100.0, abs=0.01)

    # The promo marker never appears as a league bucket.
    league_keys = {r["key"] for r in stats._breakdown(entries, lambda leg: leg.league)}
    assert league_keys == {"NBA"}


# ---- stats ----

def test_totals_core_metrics(sample_entries):
    totals = stats.compute_platform_stats(sample_entries)["totals"]
    assert totals["entries"] == 3
    assert totals["profit"] == 5.0
    assert (totals["wins"], totals["losses"], totals["pushes"]) == (1, 1, 1)
    assert totals["parlay_win_rate"] == 50.0
    assert totals["legs"] == 7
    assert totals["leg_hits"] == 4 and totals["leg_misses"] == 2 and totals["leg_pushes"] == 1
    assert totals["leg_hit_rate"] == pytest.approx(66.67, abs=0.01)
    assert totals["avg_legs_per_parlay"] == pytest.approx(2.33, abs=0.01)


def test_roi_uses_explicit_wagers(sample_entries):
    totals = stats.compute_platform_stats(sample_entries)["totals"]
    # 5 profit / 28 staked
    assert totals["roi"] == pytest.approx(17.86, abs=0.01)


def test_roi_excludes_entries_without_wager():
    entries = [
        ParlayEntry("sleeper", date(2025, 6, 1), -10.0, [Leg("A", "NBA", "Pts", "O", "M")]),
        ParlayEntry("sleeper", date(2025, 6, 2), 20.0, [Leg("B", "NBA", "Pts", "O", "H")], wager=10.0),
    ]
    totals = stats.compute_platform_stats(entries)["totals"]
    # Only the entry with column J counts toward ROI.
    assert totals["roi"] == pytest.approx(200.0, abs=0.01)


def test_avg_ev_excludes_unpriced_legs():
    priced = [ParlayEntry("sleeper", date(2025, 6, 1), 5.0, [Leg("A", "NBA", "Pts", "O", "H", payout=2.1)])]
    unpriced = [ParlayEntry("pp", date(2025, 6, 1), 5.0, [Leg("A", "NBA", "Pts", "O", "H", payout=None)])]
    assert stats.compute_platform_stats(priced)["totals"]["avg_ev"] is not None
    assert stats.compute_platform_stats(unpriced)["totals"]["avg_ev"] is None


def test_avg_ev_realized_formula_excludes_pushes():
    # Graded picks = 2 (H + M); pushes are ignored entirely.
    # ratio = sum(payout of hits) / graded = 2.0 / 2 = 1.0 -> edge 0%.
    entries = [
        ParlayEntry(
            "sleeper",
            date(2025, 6, 1),
            5.0,
            [
                Leg("A", "NBA", "Pts", "O", "H", payout=2.0),
                Leg("B", "NBA", "Pts", "O", "M", payout=1.5),
                Leg("C", "NBA", "Pts", "O", "P", payout=1.6),
            ],
        )
    ]
    assert stats.compute_platform_stats(entries)["totals"]["avg_ev"] == pytest.approx(0.0, abs=0.01)


def test_avg_ev_ignores_promo_legs():
    # Promo legs live in promo_legs and must never feed the PropRadar edge.
    entry = ParlayEntry(
        "sleeper",
        date(2025, 6, 1),
        5.0,
        [Leg("A", "NBA", "Pts", "O", "H", payout=2.0)],
        promo_legs=[Leg("P", "NBA", "Reb", "O", "H", payout=9.0, is_promo=True)],
    )
    # Only the single PropRadar hit at 2.0 counts: 2.0 / 1 - 1 = +100%.
    assert stats.compute_platform_stats([entry])["totals"]["avg_ev"] == pytest.approx(100.0, abs=0.01)


def test_avg_legs_includes_promo_legs():
    entry = ParlayEntry(
        "sleeper",
        date(2025, 6, 1),
        5.0,
        [Leg("A", "NBA", "Pts", "O", "H", payout=2.0)],
        promo_legs=[Leg("P", "NBA", "Reb", "O", "H", payout=1.5, is_promo=True)],
    )
    totals = stats.compute_platform_stats([entry])["totals"]
    assert totals["legs"] == 1  # PropRadar legs only
    assert totals["leg_hits"] == 1  # promo leg excluded from hit counts
    assert totals["avg_legs_per_parlay"] == pytest.approx(2.0, abs=0.01)


def test_parse_prizepicks_wager_column():
    from src.dashboard import config

    rows = [
        ["", "Date", "Player", "League", "Stat", "Payout", "O/U", "Result", "Profit", "Wager"],
        ["", "06/01/25", "LeBron James", "NBA", "Pts", "", "O", "H", "", ""],
        ["", "06/01/25", "Stephen Curry", "NBA", "Pts", "", "O", "H", "15.00", "25"],
        [""],
        ["", "06/02/25", "Joel Embiid", "NBA", "Reb", "", "U", "M", "-10.00", "10"],
    ]
    entries = parse_rows(rows, "prizepicks")
    assert len(entries) == 2
    assert entries[0].wager == pytest.approx(25.0)
    assert entries[0].profit == pytest.approx(15.0)
    assert entries[1].wager == pytest.approx(10.0)
    assert all(leg.payout == config.PRIZEPICKS_STANDARD_LEG_PAYOUT for leg in entries[0].legs)
    totals = stats.compute_platform_stats(entries)["totals"]
    assert totals["roi"] == pytest.approx(14.29, abs=0.01)
    # 2 hits, 1 miss at -119: (2 * 1.84) / 3 - 1 ≈ +22.7%
    assert totals["avg_ev"] == pytest.approx(22.69, abs=0.1)


def test_parse_prizepicks_ignores_legacy_line_column_for_edge():
    """Older PP sheet rows stored the prop line in column F, not a payout multiplier."""
    from src.dashboard import config

    rows = [
        ["", "11/05/23", "JaMarr Chase", "NFL", "Rec Yards", "88.5", "U", "H", ""],
        ["", "11/05/23", "Stefon Diggs", "NFL", "Rec Yards", "90.5", "U", "H", "500.00", "20"],
    ]
    entries = parse_rows(rows, "prizepicks")
    assert all(leg.payout == config.PRIZEPICKS_STANDARD_LEG_PAYOUT for leg in entries[0].legs)
    # Both legs hit at the standard -119 price: 1.84 / 1 - 1 ≈ +84%.
    assert stats.compute_platform_stats(entries)["totals"]["avg_ev"] == pytest.approx(84.03, abs=0.1)


def test_breakdowns_by_ou(sample_entries):
    by_ou = stats.compute_platform_stats(sample_entries)["breakdowns"]["by_ou"]
    keys = {row["key"] for row in by_ou}
    assert keys == {"Over", "Under"}


def test_full_stat_name_mapping_and_fallback():
    from src.dashboard import config

    assert config.full_stat_name("PRA") == "Points + Rebounds + Assists"
    assert config.full_stat_name("Pts") == "Points"
    assert config.full_stat_name("Rush yards") == "Rushing Yards"  # case-insensitive merge
    assert config.full_stat_name("anytime_touchdowns") == "Anytime Touchdowns"
    assert config.full_stat_name("weird_stat") == "Weird Stat"  # prettified fallback
    assert config.full_stat_name("") == "Unknown"


def test_low_volume_leagues_excluded_from_league_views():
    from src.dashboard import config

    legs = []
    legs += [Leg(f"big{i}", "NBA", "Pts", "O", "H") for i in range(config.MIN_LEAGUE_LEGS)]
    legs += [Leg("small1", "NHL", "SOG", "O", "H"), Leg("small2", "NHL", "SOG", "O", "M")]
    entries = [ParlayEntry("sleeper", date(2025, 6, 1), 5.0, legs)]

    breakdowns = stats.compute_platform_stats(entries)["breakdowns"]
    league_keys = {r["key"] for r in breakdowns["by_league"]}
    sport_keys = {g["sport"] for g in breakdowns["by_stat_by_sport"]}
    assert league_keys == {"NBA"}  # NHL (2 legs) dropped from the league chart
    assert sport_keys == {"NBA"}  # ...and from the per-sport stat groups


def test_breakdown_by_sport_groups_orders_and_merges():
    entries = [
        ParlayEntry(
            "sleeper",
            date(2025, 6, 1),
            5.0,
            [
                Leg("A", "NBA", "Pts", "O", "H"),
                Leg("B", "NBA", "Points", "O", "M"),  # merges with "Pts" -> Points
                Leg("C", "NBA", "PRA", "O", "H"),
                Leg("D", "NFL", "Rush Yards", "O", "H"),
                Leg("E", "NFL", "Rush yards", "O", "H"),  # merges with "Rush Yards"
            ],
        )
    ]
    # Call the helper directly so the small-sample league filter doesn't apply.
    groups = stats._breakdown_by_sport(entries)

    # Sports ordered by leg volume (NBA 3 > NFL 2).
    assert [g["sport"] for g in groups] == ["NBA", "NFL"]

    nba = groups[0]
    nba_names = {r["key"] for r in nba["stats"]}
    assert "Points" in nba_names and "Pts" not in nba_names  # variant merged + full name
    # Within a sport, sorted by hit rate desc: PRA (100%) before Points (50%).
    assert nba["stats"][0]["key"] == "Points + Rebounds + Assists"
    assert nba["stats"][0]["hit_rate"] == 100.0

    nfl = groups[1]
    assert len(nfl["stats"]) == 1  # both spellings merged
    assert nfl["stats"][0]["key"] == "Rushing Yards"
    assert nfl["stats"][0]["legs"] == 2


def test_profit_over_time_is_cumulative(sample_entries):
    series = stats.compute_platform_stats(sample_entries)["profit_over_time"]
    assert [p["cumulative"] for p in series] == [15.0, 5.0, 5.0]


def test_streaks(sample_entries):
    streaks = stats.compute_platform_stats(sample_entries)["streaks"]
    assert streaks["longest_win"] == 1
    assert streaks["longest_loss"] == 1


def test_recent_and_top_lists(sample_entries):
    block = stats.compute_platform_stats(sample_entries)
    assert len(block["recent"]) == 3
    assert block["best"][0]["profit"] == 15.0
    assert block["worst"][0]["profit"] == -10.0


def test_empty_entries_safe():
    block = stats.compute_platform_stats([])
    assert block["totals"]["entries"] == 0
    assert block["totals"]["roi"] is None
    assert block["recent"] == []


# ---- assumed Sleeper promo legs ----


def test_assumed_promo_skips_when_disabled():
    entry = ParlayEntry("sleeper", date(2025, 6, 1), 5.0, [Leg("A", "NBA", "Pts", "O", "H", payout=1.5)])
    apply_assumed_sleeper_promos([entry], enabled=False)
    assert entry.promo_legs == []


def test_assumed_promo_leg_when_enabled():
    entry = ParlayEntry("sleeper", date(2025, 6, 1), 5.0, [Leg("A", "NBA", "Pts", "O", "H", payout=1.5)])
    apply_assumed_sleeper_promos([entry], enabled=True)
    assert len(entry.promo_legs) == 1
    assert entry.promo_legs[0].is_promo is True
    assert entry.total_legs == 2  # 1 PropRadar pick + 1 assumed promo
    # The assumed promo must not pollute hit-rate or Est. Edge (no result/payout).
    totals = stats.compute_platform_stats([entry])["totals"]
    assert totals["legs"] == 1
    assert totals["leg_hits"] == 1
    assert totals["avg_ev"] == pytest.approx(50.0, abs=0.01)  # 1.5/1 - 1


def test_assumed_promo_not_added_when_sheet_has_one():
    rows = [
        ["", "06/05/25", "Player A", "NBA", "Pts", "1.5", "O", "H", ""],
        ["", "06/05/25", "Promo Guy", "Line Discount", "Reb", "1.4", "O", "H", "$12.00"],
    ]
    entry = parse_rows(rows, "sleeper")[0]
    assert len(entry.promo_legs) == 1
    apply_assumed_sleeper_promos([entry], enabled=True)
    assert len(entry.promo_legs) == 1
    assert entry.promo_legs[0].name == "Promo Guy"
