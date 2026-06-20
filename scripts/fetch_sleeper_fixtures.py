#!/usr/bin/env python3
"""Fetch trimmed Sleeper API responses and save them under tests/fixtures/sleeper/."""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import requests

from fixture_config import FIXTURES_DIR, LEAGUES, default_date_range, sleeper_auth, write_fixture

SLEEPER_BASE = "https://api.sleeper.app"
GRAPHQL_URL = f"{SLEEPER_BASE}/graphql"
MAX_LINES = 12
MAX_PROMOS = 20

AVAILABLE_LINE_PROMOTIONS_QUERY = """
query available_line_promotions($include_boosts: Boolean) {
  available_line_promotions(include_boosts: $include_boosts) {
    sport
    subject_id
    wager_type
    type
    game_id
  }
}
"""


def _get(url: str, *, params: dict | None = None, timeout: int = 30) -> requests.Response:
    resp = requests.get(url, params=params, timeout=timeout)
    if resp.status_code != 200:
        raise SystemExit(f"Request failed: GET {url}\nHTTP {resp.status_code}: {resp.text[:500]}")
    return resp


def _post_graphql(operation: str, query: str, variables: dict, auth: str) -> dict:
    headers = {
        "accept": "application/json",
        "authorization": auth,
        "content-type": "application/json",
        "x-sleeper-graphql-op": operation,
    }
    resp = requests.post(
        GRAPHQL_URL,
        headers=headers,
        json={"operationName": operation, "query": query, "variables": variables},
        timeout=30,
    )
    if resp.status_code != 200:
        raise SystemExit(
            f"GraphQL {operation} failed: HTTP {resp.status_code}: {resp.text[:500]}"
        )
    payload = resp.json()
    if payload.get("errors"):
        raise SystemExit(f"GraphQL {operation} errors: {payload['errors']}")
    return payload


def fetch_lines(sleeper_league: str, start_day: date, end_day: date) -> list[dict]:
    resp = _get(
        f"{SLEEPER_BASE}/lines/available",
        params={
            "sports[]": sleeper_league,
            "date_from": start_day.isoformat(),
            "date_to": end_day.isoformat(),
            "dynamic": "true",
            "eg": "5.control",
        },
    )
    lines = resp.json()
    print(f"Sleeper lines/available: {len(lines)} returned")
    return lines


def fetch_players(sleeper_league: str) -> dict:
    resp = _get(f"{SLEEPER_BASE}/v1/players/{sleeper_league}")
    players = resp.json()
    print(f"Sleeper v1/players/{sleeper_league}: {len(players)} returned")
    return players


def fetch_promos() -> list[dict]:
    resp = _get(f"{SLEEPER_BASE}/lines/promos")
    promos = resp.json()
    print(f"Sleeper lines/promos: {len(promos)} returned")
    return promos


def fetch_available_line_promotions(auth: str) -> list[dict]:
    payload = _post_graphql(
        "available_line_promotions",
        AVAILABLE_LINE_PROMOTIONS_QUERY,
        {"include_boosts": True},
        auth,
    )
    promos = payload.get("data", {}).get("available_line_promotions") or []
    print(f"Sleeper graphql available_line_promotions: {len(promos)} returned")
    return promos


def promo_pair_subject_ids(promos: list[dict]) -> set[str]:
    '''Subjects with both normal and promotional rows, as required by getPlayerPromos().'''
    by_subject: dict[str, set[str]] = {}
    for promo in promos:
        subject_id = promo.get("subject_id")
        if not subject_id:
            continue
        by_subject.setdefault(subject_id, set()).add(promo.get("line_type"))
    return {
        subject_id
        for subject_id, line_types in by_subject.items()
        if "normal" in line_types and line_types - {"normal"}
    }


def graphql_subject_ids_for_league(graphql_promos: list[dict], sleeper_league: str) -> set[str]:
    return {
        promo["subject_id"]
        for promo in graphql_promos
        if promo.get("subject_id") and promo.get("sport") == sleeper_league
    }


def _promo_rows_for_subjects(promos: list[dict], subject_ids: list[str], *, limit: int) -> list[dict]:
    selected: list[dict] = []
    for subject_id in subject_ids:
        rows = [promo for promo in promos if promo.get("subject_id") == subject_id]
        if not rows:
            continue
        if selected and len(selected) + len(rows) > limit:
            break
        selected.extend(rows)
    return selected[:limit]


def trim_lines(
    lines: list[dict],
    sleeper_stats: list[str],
    *,
    limit: int,
    min_teams: int = 2,
) -> list[dict]:
    def keep(line: dict) -> bool:
        return (
            line.get("game_status") == "pre_game"
            and line.get("line_type") == "normal"
            and line.get("wager_type") in sleeper_stats
            and line.get("outcome_type") == "over_under"
            and line.get("subject_id")
        )

    def line_team(line: dict) -> str | None:
        for option in line.get("options", []):
            team = option.get("subject_team")
            if team:
                return team
        return None

    eligible = [line for line in lines if keep(line)]
    selected: list[dict] = []
    seen_stats: set[str] = set()
    teams: set[str] = set()

    for stat in sleeper_stats:
        if len(selected) >= limit:
            break
        candidates = [line for line in eligible if line.get("wager_type") == stat and line not in selected]
        if not candidates:
            continue
        candidates.sort(key=lambda line: (0 if line_team(line) not in teams else 1, line.get("subject_id", "")))
        pick = candidates[0]
        selected.append(pick)
        seen_stats.add(stat)
        team = line_team(pick)
        if team:
            teams.add(team)

    if len(teams) < min_teams:
        for line in eligible:
            if line in selected:
                continue
            team = line_team(line)
            if team and team not in teams:
                selected.append(line)
                teams.add(team)
                break

    if len(teams) < min_teams:
        raise SystemExit(
            f"Could not find lines from {min_teams} teams; got {sorted(teams) or ['<none>']}"
        )

    for line in eligible:
        if len(selected) >= limit:
            break
        if line in selected:
            continue
        team = line_team(line)
        if team and team not in teams:
            selected.append(line)
            teams.add(team)

    return selected[:limit]


def trim_players(all_players: dict, subject_ids: set[str]) -> dict:
    return {
        player_id: {
            "full_name": player["full_name"],
            "team": player.get("team"),
            "position": player.get("position"),
        }
        for player_id, player in all_players.items()
        if player_id in subject_ids and player.get("full_name")
    }


def trim_promos(
    promos: list[dict],
    line_subject_ids: set[str],
    *,
    limit: int,
    graphql_promos: list[dict] | None = None,
    sleeper_league: str | None = None,
) -> list[dict]:
    pair_ids = promo_pair_subject_ids(promos)

    def ordered_subjects(candidates: set[str]) -> list[str]:
        eligible = [subject_id for subject_id in sorted(candidates) if subject_id in pair_ids]
        if graphql_promos and sleeper_league:
            gql_ids = graphql_subject_ids_for_league(graphql_promos, sleeper_league)
            gql_first = [subject_id for subject_id in sorted(gql_ids) if subject_id in pair_ids]
            line_first = [subject_id for subject_id in sorted(line_subject_ids) if subject_id in pair_ids]
            seen: set[str] = set()
            ordered: list[str] = []
            for subject_id in gql_first + line_first:
                if subject_id not in seen:
                    seen.add(subject_id)
                    ordered.append(subject_id)
            return ordered
        return eligible

    preferred = line_subject_ids & pair_ids
    if graphql_promos and sleeper_league:
        preferred |= graphql_subject_ids_for_league(graphql_promos, sleeper_league) & pair_ids

    if preferred:
        return _promo_rows_for_subjects(promos, ordered_subjects(preferred), limit=limit)

    # Fall back to one promo player pair if none overlap with selected lines or GraphQL.
    by_subject: dict[str, list[dict]] = {}
    for promo in promos:
        subject_id = promo.get("subject_id")
        if subject_id:
            by_subject.setdefault(subject_id, []).append(promo)

    for subject_id, items in by_subject.items():
        line_types = {item.get("line_type") for item in items}
        if "normal" in line_types and len(line_types) > 1:
            return items[:limit]

    return promos[: min(limit, 5)]


def trim_parlays(parlays: list[dict] | None, *, limit: int = 1) -> list[dict]:
    if not parlays:
        return []
    trimmed = []
    for parlay in parlays[:limit]:
        legs = []
        for leg in parlay.get("legs", [])[:3]:
            line = copy.deepcopy(leg.get("line", {}))
            if "score" in line and isinstance(line["score"], dict):
                line["score"] = {
                    key: line["score"][key]
                    for key in ("date", "game_id", "sport", "start_time", "status")
                    if key in line["score"]
                }
            legs.append(
                {
                    "line_id": leg.get("line_id"),
                    "status": leg.get("status"),
                    "line": {
                        "line_id": line.get("line_id"),
                        "subject_id": line.get("subject_id"),
                        "wager_type": line.get("wager_type"),
                        "outcome_value": line.get("outcome_value"),
                        "payout_multiplier": line.get("payout_multiplier"),
                        "metadata": line.get("metadata", {}),
                        "score": line.get("score"),
                    },
                }
            )
        trimmed.append(
            {
                "parlay_id": parlay.get("parlay_id"),
                "status": parlay.get("status"),
                "multiplier": parlay.get("multiplier"),
                "legs": legs,
            }
        )
    return trimmed


def fetch_graphql_fixtures(
    output_dir: Path,
    auth: str,
    *,
    sleeper_league: str,
    line_promotions: list[dict] | None = None,
    aligned_promo_subject_ids: set[str] | None = None,
) -> None:
    graphql_dir = output_dir / "graphql"

    parlays_query = """
    query my_parlays($limit: Int, $status_filter: [String]) {
      my_parlays(limit: $limit, status_filter: $status_filter) {
        parlay_id
        status
        multiplier
        legs {
          line_id
          status
          line {
            line_id
            subject_id
            wager_type
            outcome_value
            payout_multiplier
            metadata
            score { date game_id sport start_time status }
          }
        }
      }
    }
    """
    parlays_payload = _post_graphql(
        "my_parlays",
        parlays_query,
        {"limit": 5, "status_filter": ["pending"]},
        auth,
    )
    write_fixture(
        graphql_dir / "my_parlays_pending.json",
        {
            "meta": {"source": "sleeper graphql", "operation": "my_parlays"},
            "data": {
                "my_parlays": trim_parlays(parlays_payload.get("data", {}).get("my_parlays")),
            },
        },
    )

    if line_promotions is None:
        line_promotions = fetch_available_line_promotions(auth)

    league_promos = [
        promo for promo in line_promotions if promo.get("sport") == sleeper_league
    ]
    if aligned_promo_subject_ids:
        league_promos = [
            promo
            for promo in league_promos
            if promo.get("subject_id") in aligned_promo_subject_ids
        ] or league_promos

    write_fixture(
        graphql_dir / "available_line_promotions.json",
        {
            "meta": {
                "source": "sleeper graphql",
                "operation": "available_line_promotions",
                "sleeper_league": sleeper_league,
                "count": len(league_promos),
            },
            "data": {"available_line_promotions": league_promos[:MAX_PROMOS]},
        },
    )


def build_fixtures(
    league: str,
    *,
    start_day: date,
    end_day: date,
    output_dir: Path = FIXTURES_DIR / "sleeper",
    include_graphql: bool = False,
    max_lines: int = MAX_LINES,
    max_promos: int = MAX_PROMOS,
) -> None:
    config = LEAGUES[league]
    sleeper_league = config["sleeper_league"]
    prefix = league.lower()

    lines = fetch_lines(sleeper_league, start_day, end_day)
    trimmed_lines = trim_lines(lines, config["sleeper_stats"], limit=max_lines)
    if not trimmed_lines:
        raise SystemExit(
            f"No pre_game normal lines found for {league} between {start_day} and {end_day}."
        )

    subject_ids = {line["subject_id"] for line in trimmed_lines if line.get("subject_id")}
    teams = sorted(
        {
            option.get("subject_team")
            for line in trimmed_lines
            for option in line.get("options", [])
            if option.get("subject_team")
        }
    )

    auth = sleeper_auth()
    graphql_line_promotions = None
    if include_graphql and auth:
        graphql_line_promotions = fetch_available_line_promotions(auth)
    elif include_graphql:
        print("Skipping GraphQL fixtures: SLEEPER_AUTH is not set in .env")

    all_line_promos = fetch_promos()
    promos = trim_promos(
        all_line_promos,
        subject_ids,
        limit=max_promos,
        graphql_promos=graphql_line_promotions,
        sleeper_league=sleeper_league,
    )
    promo_subject_ids = {promo["subject_id"] for promo in promos if promo.get("subject_id")}
    all_subject_ids = subject_ids | promo_subject_ids

    all_players = fetch_players(sleeper_league)
    trimmed_players = trim_players(all_players, all_subject_ids)
    if promo_subject_ids - set(trimmed_players):
        missing = sorted(promo_subject_ids - set(trimmed_players))
        raise SystemExit(
            f"Promo subject_id(s) missing from players response: {missing}. "
            "Re-fetch or trim promos to subjects present in v1/players."
        )

    write_fixture(
        output_dir / f"{prefix}_lines_available.json",
        {
            "meta": {
                "source": "sleeper.app/lines/available",
                "league": league,
                "sleeper_league": sleeper_league,
                "date_from": start_day.isoformat(),
                "date_to": end_day.isoformat(),
                "count": len(trimmed_lines),
                "teams": teams,
            },
            "lines": trimmed_lines,
        },
    )
    write_fixture(
        output_dir / f"{prefix}_players.json",
        {
            "meta": {
                "source": f"sleeper.app/v1/players/{sleeper_league}",
                "league": league,
                "count": len(trimmed_players),
            },
            "players": trimmed_players,
        },
    )
    write_fixture(
        output_dir / f"{prefix}_lines_promos.json",
        {
            "meta": {
                "source": "sleeper.app/lines/promos",
                "league": league,
                "count": len(promos),
                "subject_ids": sorted(promo_subject_ids),
            },
            "promos": promos,
        },
    )

    if include_graphql and auth:
        fetch_graphql_fixtures(
            output_dir,
            auth,
            sleeper_league=sleeper_league,
            line_promotions=graphql_line_promotions,
            aligned_promo_subject_ids=promo_subject_ids,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--league",
        default="NBA",
        choices=sorted(LEAGUES),
        help="League to fetch (default: NBA)",
    )
    parser.add_argument(
        "--date-from",
        type=date.fromisoformat,
        help="Start date for lines/available (default: today)",
    )
    parser.add_argument(
        "--date-to",
        type=date.fromisoformat,
        help="End date for lines/available (default: today + 3 days)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=FIXTURES_DIR / "sleeper",
        help="Directory for fixture JSON files",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=MAX_LINES,
        help="Maximum number of lines to keep",
    )
    parser.add_argument(
        "--max-promos",
        type=int,
        default=MAX_PROMOS,
        help="Maximum promo rows to keep",
    )
    parser.add_argument(
        "--include-graphql",
        action="store_true",
        help="Also fetch authenticated GraphQL fixtures (requires SLEEPER_AUTH)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    date_from = args.date_from
    date_to = args.date_to
    if date_from is None or date_to is None:
        default_start, default_end = default_date_range()
        date_from = date_from or default_start
        date_to = date_to or default_end

    build_fixtures(
        args.league,
        start_day=date_from,
        end_day=date_to,
        output_dir=args.output_dir,
        include_graphql=args.include_graphql,
        max_lines=args.max_lines,
        max_promos=args.max_promos,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
