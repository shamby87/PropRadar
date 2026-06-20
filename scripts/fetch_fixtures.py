#!/usr/bin/env python3
"""Fetch Sleeper and the-odds-api test fixtures."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fixture_config import FIXTURES_DIR, LEAGUES, default_date_range
from fetch_odds_api_fixtures import build_fixtures as build_odds_fixtures
from fetch_sleeper_fixtures import build_fixtures as build_sleeper_fixtures


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--league",
        default="NBA",
        choices=sorted(LEAGUES),
        help="League to fetch (default: NBA)",
    )
    parser.add_argument(
        "--start-day",
        type=date.fromisoformat,
        help="Start date for event/line filtering (default: today)",
    )
    parser.add_argument(
        "--end-day",
        type=date.fromisoformat,
        help="End date for event/line filtering (default: today + 3 days)",
    )
    parser.add_argument(
        "--odds-api-only",
        action="store_true",
        help="Fetch only the-odds-api fixtures",
    )
    parser.add_argument(
        "--sleeper-only",
        action="store_true",
        help="Fetch only Sleeper fixtures",
    )
    parser.add_argument(
        "--include-graphql",
        action="store_true",
        help="Include authenticated Sleeper GraphQL fixtures",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.odds_api_only and args.sleeper_only:
        raise SystemExit("Use at most one of --odds-api-only or --sleeper-only.")

    start_day = args.start_day
    end_day = args.end_day
    if start_day is None or end_day is None:
        default_start, default_end = default_date_range()
        start_day = start_day or default_start
        end_day = end_day or default_end

    fetch_odds = not args.sleeper_only
    fetch_sleeper = not args.odds_api_only

    if fetch_odds:
        build_odds_fixtures(
            args.league,
            start_day=start_day,
            end_day=end_day,
            output_dir=FIXTURES_DIR / "odds_api",
        )
    if fetch_sleeper:
        build_sleeper_fixtures(
            args.league,
            start_day=start_day,
            end_day=end_day,
            output_dir=FIXTURES_DIR / "sleeper",
            include_graphql=args.include_graphql,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
