"""Compute PropRadar performance analytics from parsed parlay entries.

All functions here are pure and operate on lists of
:class:`~src.dashboard.sheet_reader.ParlayEntry`, so they are fully unit
testable without any network access.
"""
from __future__ import annotations

from collections import defaultdict

from . import config
from .sheet_reader import ParlayEntry


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def _entry_wager(entry: ParlayEntry) -> float | None:
    """Return the recorded stake for ROI, or None when column J is missing."""
    return entry.wager


def _roi(entries: list[ParlayEntry]) -> float | None:
    """Return ROI percent over entries with a recorded stake in column J."""
    known = [(e, w) for e in entries if (w := _entry_wager(e)) is not None]
    if not known:
        return None
    total_wager = sum(w for _, w in known)
    total_profit = sum(e.profit for e, _ in known)
    if total_wager == 0:
        return None
    return (total_profit / total_wager) * 100.0


def _avg_ev(entries: list[ParlayEntry]) -> float | None:
    """Realized average per-pick edge (percent) over PropRadar's own picks.

    edge = (sum of payout multipliers for graded picks that HIT / number of
    graded PropRadar picks) - 1, expressed as a percentage. This treats each
    pick as a standalone $1 bet: a value above 0 means the picks returned more
    than the stake on average. Pushes and unpriced legs (e.g. PrizePicks) are
    excluded; promo legs are not PropRadar picks and never counted.
    """
    graded_picks = 0
    won_payout = 0.0
    for entry in entries:
        for leg in entry.legs:
            if leg.payout is None or leg.payout <= 0:
                continue
            if leg.result == "H":
                graded_picks += 1
                won_payout += leg.payout
            elif leg.result == "M":
                graded_picks += 1
    if graded_picks == 0:
        return None
    return (won_payout / graded_picks - 1.0) * 100.0


def _totals(entries: list[ParlayEntry]) -> dict:
    wins = sum(1 for e in entries if e.outcome == "win")
    losses = sum(1 for e in entries if e.outcome == "loss")
    pushes = sum(1 for e in entries if e.outcome == "push")

    legs = [leg for e in entries for leg in e.legs]
    leg_hits = sum(1 for leg in legs if leg.result == "H")
    leg_misses = sum(1 for leg in legs if leg.result == "M")
    leg_pushes = sum(1 for leg in legs if leg.result == "P")

    graded_parlays = wins + losses
    graded_legs = leg_hits + leg_misses

    # Avg legs reflects the real parlay size, including recovered promo legs.
    total_legs = sum(e.total_legs for e in entries)

    roi = _roi(entries)
    ordered = sorted(entries, key=lambda e: e.date)

    return {
        "profit": _round(sum(e.profit for e in entries)),
        "entries": len(entries),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "parlay_win_rate": _round(100.0 * wins / graded_parlays) if graded_parlays else None,
        "legs": len(legs),
        "leg_hits": leg_hits,
        "leg_misses": leg_misses,
        "leg_pushes": leg_pushes,
        "leg_hit_rate": _round(100.0 * leg_hits / graded_legs) if graded_legs else None,
        "avg_legs_per_parlay": _round(total_legs / len(entries)) if entries else None,
        "roi": _round(roi),
        "avg_ev": _round(_avg_ev(entries)),
        "date_start": ordered[0].date.strftime("%m/%d/%y") if ordered else None,
        "date_end": ordered[-1].date.strftime("%m/%d/%y") if ordered else None,
    }


def _breakdown(entries: list[ParlayEntry], key) -> list[dict]:
    buckets: dict[str, dict] = defaultdict(lambda: {"hits": 0, "misses": 0, "pushes": 0, "legs": 0})
    for entry in entries:
        for leg in entry.legs:
            bucket_key = key(leg) or "Unknown"
            bucket = buckets[bucket_key]
            bucket["legs"] += 1
            if leg.result == "H":
                bucket["hits"] += 1
            elif leg.result == "M":
                bucket["misses"] += 1
            else:
                bucket["pushes"] += 1

    rows = []
    for name, bucket in buckets.items():
        graded = bucket["hits"] + bucket["misses"]
        rows.append({
            "key": name,
            "legs": bucket["legs"],
            "hits": bucket["hits"],
            "misses": bucket["misses"],
            "pushes": bucket["pushes"],
            "hit_rate": _round(100.0 * bucket["hits"] / graded) if graded else None,
        })
    rows.sort(key=lambda r: r["legs"], reverse=True)
    return rows


def _breakdown_by_sport(entries: list[ParlayEntry]) -> list[dict]:
    """Stat hit-rate breakdown grouped by sport, then sorted by hit rate.

    Stats use their full display names (merging abbreviation variants). Sports
    are ordered by total leg volume (most active first); within each sport stats
    are sorted by hit rate descending, with ungraded stats last.
    """
    sports: dict[str, dict[str, dict]] = defaultdict(
        lambda: defaultdict(lambda: {"hits": 0, "misses": 0, "pushes": 0, "legs": 0})
    )
    for entry in entries:
        for leg in entry.legs:
            sport = (leg.league or "Unknown").strip() or "Unknown"
            name = config.full_stat_name(leg.stat)
            bucket = sports[sport][name]
            bucket["legs"] += 1
            if leg.result == "H":
                bucket["hits"] += 1
            elif leg.result == "M":
                bucket["misses"] += 1
            else:
                bucket["pushes"] += 1

    groups = []
    for sport, stat_buckets in sports.items():
        stat_rows = []
        for name, bucket in stat_buckets.items():
            graded = bucket["hits"] + bucket["misses"]
            stat_rows.append({
                "key": name,
                "legs": bucket["legs"],
                "hits": bucket["hits"],
                "misses": bucket["misses"],
                "pushes": bucket["pushes"],
                "hit_rate": _round(100.0 * bucket["hits"] / graded) if graded else None,
            })
        stat_rows.sort(key=lambda r: (r["hit_rate"] is None, -(r["hit_rate"] or 0.0)))
        groups.append({
            "sport": sport,
            "legs": sum(r["legs"] for r in stat_rows),
            "stats": stat_rows,
        })

    groups.sort(key=lambda g: g["legs"], reverse=True)
    return groups


def _profit_over_time(entries: list[ParlayEntry]) -> list[dict]:
    daily: dict = defaultdict(float)
    for entry in entries:
        daily[entry.date] += entry.profit

    series = []
    cumulative = 0.0
    for day in sorted(daily):
        cumulative += daily[day]
        series.append({
            "date": day.isoformat(),
            "profit": _round(daily[day]),
            "cumulative": _round(cumulative),
        })
    return series


def _streaks(entries: list[ParlayEntry]) -> dict:
    ordered = [e for e in sorted(entries, key=lambda e: e.date) if e.outcome != "push"]

    longest_win = longest_loss = 0
    run_type = None
    run_len = 0
    for entry in ordered:
        if entry.outcome == run_type:
            run_len += 1
        else:
            run_type = entry.outcome
            run_len = 1
        if run_type == "win":
            longest_win = max(longest_win, run_len)
        else:
            longest_loss = max(longest_loss, run_len)

    current = {"type": run_type, "length": run_len} if ordered else {"type": None, "length": 0}
    return {
        "current": current,
        "longest_win": longest_win,
        "longest_loss": longest_loss,
    }


def _top_entries(entries: list[ParlayEntry], size: int) -> tuple[list[dict], list[dict]]:
    ranked = sorted(entries, key=lambda e: e.profit, reverse=True)
    best = [e.to_dict() for e in ranked[:size]]
    worst = [e.to_dict() for e in sorted(entries, key=lambda e: e.profit)[:size]]
    return best, worst


def compute_platform_stats(
    entries: list[ParlayEntry],
    summaries: dict | None = None,
) -> dict:
    """Full analytics block for a single platform (or the combined set)."""
    recent = sorted(entries, key=lambda e: (e.date, e.profit), reverse=True)[: config.RECENT_LIMIT]
    best, worst = _top_entries(entries, config.TOP_LIST_SIZE)
    min_legs = config.MIN_LEAGUE_LEGS
    by_league = [r for r in _breakdown(entries, lambda leg: leg.league) if r["legs"] >= min_legs]
    by_stat_by_sport = [g for g in _breakdown_by_sport(entries) if g["legs"] >= min_legs]
    return {
        "totals": _totals(entries),
        "breakdowns": {
            "by_league": by_league,
            "by_stat": _breakdown(entries, lambda leg: leg.stat),
            "by_stat_by_sport": by_stat_by_sport,
            "by_ou": _breakdown(entries, lambda leg: {"O": "Over", "U": "Under"}.get(leg.ou, leg.ou)),
        },
        "profit_over_time": _profit_over_time(entries),
        "streaks": _streaks(entries),
        "best": best,
        "worst": worst,
        "recent": [e.to_dict() for e in recent],
        "sheet_summaries": summaries or {},
    }
