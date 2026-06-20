#!/usr/bin/env python3
"""Build a small PrizePicks fixture from src/prizePicks/data.txt for tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "prizePicks" / "data.txt"
OUTPUT = ROOT / "tests" / "fixtures" / "prizepicks" / "nba_projections.json"

LEAGUE = "NBA"
NBA_PP_STATS = ["Points", "Pts+Rebs+Asts", "Pts+Rebs", "Pts+Asts", "Rebounds", "Assists"]
ODDS_TYPES = ("standard", "goblin")


def _merged_frames(raw: dict) -> pd.DataFrame:
    data = pd.json_normalize(raw["data"], max_level=3)
    included = pd.json_normalize(raw["included"], max_level=3)
    players = included[included["type"] == "new_player"].copy().dropna(axis=1)
    return pd.merge(
        data,
        players,
        how="left",
        left_on=["relationships.new_player.data.id", "relationships.new_player.data.type"],
        right_on=["id", "type"],
        suffixes=("", "_new_player"),
    )


def _pick_one(
    merged: pd.DataFrame,
    *,
    odds_type: str,
    stat_type: str,
    selected: set[str],
) -> str | None:
    rows = merged[
        (merged["attributes.odds_type"] == odds_type)
        & (merged["attributes.status"] == "pre_game")
        & (merged["attributes.league"] == LEAGUE)
        & (merged["attributes.stat_type"] == stat_type)
        & (~merged["id"].isin(selected))
    ]
    if rows.empty:
        return None
    return rows.iloc[0]["id"]


def _pick_edge_cases(merged: pd.DataFrame, selected: set[str]) -> list[str]:
    extras: list[str] = []

    combo = merged[
        (merged["attributes.league"] == LEAGUE)
        & (merged["attributes.stat_type"] == "Points (Combo)")
        & (merged["attributes.odds_type"] == "standard")
        & (~merged["id"].isin(selected))
    ]
    if not combo.empty:
        extras.append(combo.iloc[0]["id"])

    demon = merged[
        (merged["attributes.league"] == LEAGUE)
        & (merged["attributes.odds_type"] == "demon")
        & (merged["attributes.stat_type"].isin(NBA_PP_STATS))
        & (~merged["id"].isin(selected))
    ]
    if not demon.empty:
        extras.append(demon.iloc[0]["id"])

    return extras


def _pick_ids(merged: pd.DataFrame) -> list[str]:
    selected: list[str] = []

    for odds_type in ODDS_TYPES:
        for stat in NBA_PP_STATS:
            row_id = _pick_one(merged, odds_type=odds_type, stat_type=stat, selected=set(selected))
            if row_id:
                selected.append(row_id)

    if not any(
        merged.loc[merged["id"].isin(selected), "attributes.odds_type"].eq("standard")
    ):
        raise RuntimeError("No NBA standard projections found in data.txt")
    if not any(
        merged.loc[merged["id"].isin(selected), "attributes.odds_type"].eq("goblin")
    ):
        raise RuntimeError("No NBA goblin projections found in data.txt")

    selected.extend(_pick_edge_cases(merged, set(selected)))
    return selected


def _collect_included(raw: dict, data_ids: set[str]) -> list[dict]:
    player_ids = set()
    for item in raw["data"]:
        if item["id"] not in data_ids:
            continue
        ref = item.get("relationships", {}).get("new_player", {}).get("data")
        if ref:
            player_ids.add(ref["id"])

    return [item for item in raw["included"] if item.get("type") == "new_player" and item["id"] in player_ids]


def build_fixture(source: Path = SOURCE) -> dict:
    raw = json.loads(source.read_text())
    merged = _merged_frames(raw)
    selected_ids = set(_pick_ids(merged))

    counts = merged.loc[merged["id"].isin(selected_ids), "attributes.odds_type"].value_counts().to_dict()
    fixture = {
        "data": [item for item in raw["data"] if item["id"] in selected_ids],
        "included": _collect_included(raw, selected_ids),
        "meta": {
            "source": source.name,
            "league": LEAGUE,
            "odds_types": counts,
            "note": "Trimmed snapshot for pp.py (standard) and gobbyFinder.py (goblin) tests",
        },
    }
    return fixture


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT

    fixture = build_fixture(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixture, indent=2))
    print(
        f"Wrote {len(fixture['data'])} projections and {len(fixture['included'])} players "
        f"to {output} ({fixture['meta']['odds_types']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
