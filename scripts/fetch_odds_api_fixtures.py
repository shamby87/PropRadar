#!/usr/bin/env python3
"""Fetch trimmed the-odds-api responses and save them under tests/fixtures/odds_api/."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import requests

from fixture_config import FIXTURES_DIR, LEAGUES, api_keys, default_date_range, write_fixture

ODDS_BASE = "https://api.the-odds-api.com/v4"
REGIONS = "us"
ODDS_FORMAT = "decimal"
DATE_FORMAT = "iso"
MAX_EVENTS = 3
MAX_BOOKMAKERS = 3


def _get(url: str, *, params: dict) -> requests.Response:
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(
            f"Request failed: GET {url}\n"
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )
    return resp


def fetch_events(sport_key: str, api_key: str) -> list[dict]:
    resp = _get(
        f"{ODDS_BASE}/sports/{sport_key}/odds",
        params={
            "api_key": api_key,
            "regions": REGIONS,
            "markets": "h2h",
            "oddsFormat": ODDS_FORMAT,
            "dateFormat": DATE_FORMAT,
        },
    )
    remaining = resp.headers.get("x-requests-remaining", "?")
    print(f"the-odds-api events: {len(resp.json())} returned, {remaining} requests remaining")
    return resp.json()


def fetch_event_odds(sport_key: str, event_id: str, market: str, api_key: str) -> dict:
    resp = _get(
        f"{ODDS_BASE}/sports/{sport_key}/events/{event_id}/odds",
        params={
            "api_key": api_key,
            "regions": REGIONS,
            "markets": market,
            "oddsFormat": ODDS_FORMAT,
            "dateFormat": DATE_FORMAT,
        },
    )
    remaining = resp.headers.get("x-requests-remaining", "?")
    print(f"the-odds-api {market} for {event_id}: {remaining} requests remaining")
    return resp.json()


def trim_events(events: list[dict], *, start_day: date, end_day: date, limit: int) -> list[dict]:
    trimmed = []
    for event in events:
        event_day = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00")).date()
        if start_day <= event_day <= end_day:
            trimmed.append(
                {
                    "id": event["id"],
                    "sport_key": event.get("sport_key"),
                    "commence_time": event["commence_time"],
                    "home_team": event.get("home_team"),
                    "away_team": event.get("away_team"),
                }
            )
        if len(trimmed) >= limit:
            break
    if not trimmed:
        trimmed = [
            {
                "id": event["id"],
                "sport_key": event.get("sport_key"),
                "commence_time": event["commence_time"],
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
            }
            for event in events[:limit]
        ]
    return trimmed


def trim_event_odds(payload: dict, *, max_bookmakers: int) -> dict:
    bookmakers = payload.get("bookmakers", [])[:max_bookmakers]
    for book in bookmakers:
        for market in book.get("markets", []):
            market["outcomes"] = market.get("outcomes", [])[:40]
    return {
        "id": payload.get("id"),
        "sport_key": payload.get("sport_key"),
        "commence_time": payload.get("commence_time"),
        "home_team": payload.get("home_team"),
        "away_team": payload.get("away_team"),
        "bookmakers": bookmakers,
    }


def build_fixtures(
    league: str,
    *,
    start_day: date,
    end_day: date,
    output_dir: Path = FIXTURES_DIR / "odds_api",
    max_events: int = MAX_EVENTS,
    max_bookmakers: int = MAX_BOOKMAKERS,
) -> None:
    config = LEAGUES[league]
    api_key = api_keys()[0]
    sport_key = config["sport_key"]
    prefix = league.lower()

    events = fetch_events(sport_key, api_key)
    trimmed_events = trim_events(
        events,
        start_day=start_day,
        end_day=end_day,
        limit=max_events,
    )
    write_fixture(
        output_dir / f"{prefix}_events.json",
        {
            "meta": {
                "source": "the-odds-api.com",
                "sport_key": sport_key,
                "start_day": start_day.isoformat(),
                "end_day": end_day.isoformat(),
                "count": len(trimmed_events),
            },
            "events": trimmed_events,
        },
    )

    if not trimmed_events:
        raise SystemExit("No events returned; cannot fetch event odds fixtures.")

    event_id = trimmed_events[0]["id"]
    markets = list(config["odds_api_markets"])
    if include_alternate := config.get("odds_api_alternate_markets"):
        markets.extend(include_alternate)

    for market in markets:
        odds = fetch_event_odds(sport_key, event_id, market, api_key)
        write_fixture(
            output_dir / f"{prefix}_{market}.json",
            {
                "meta": {
                    "source": "the-odds-api.com",
                    "sport_key": sport_key,
                    "event_id": event_id,
                    "market": market,
                    "alternate": market.endswith("_alternate"),
                },
                "event": trim_event_odds(odds, max_bookmakers=max_bookmakers),
            },
        )

    write_fixture(
        output_dir / "out_of_usage_credits.json",
        {
            "meta": {
                "source": "the-odds-api.com",
                "note": "Static error shape for tests; not fetched live",
            },
            "error_code": "OUT_OF_USAGE_CREDITS",
            "message": "Usage quota has been reached",
        },
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
        "--start-day",
        type=date.fromisoformat,
        help="Include events on/after this date (default: today)",
    )
    parser.add_argument(
        "--end-day",
        type=date.fromisoformat,
        help="Include events on/before this date (default: today + 3 days)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=FIXTURES_DIR / "odds_api",
        help="Directory for fixture JSON files",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=MAX_EVENTS,
        help="Maximum number of events to keep",
    )
    parser.add_argument(
        "--max-bookmakers",
        type=int,
        default=MAX_BOOKMAKERS,
        help="Maximum bookmakers per event odds response",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start_day = args.start_day
    end_day = args.end_day
    if start_day is None or end_day is None:
        default_start, default_end = default_date_range()
        start_day = start_day or default_start
        end_day = end_day or default_end

    build_fixtures(
        args.league,
        start_day=start_day,
        end_day=end_day,
        output_dir=args.output_dir,
        max_events=args.max_events,
        max_bookmakers=args.max_bookmakers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
