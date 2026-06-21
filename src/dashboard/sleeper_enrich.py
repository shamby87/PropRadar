"""Enrich sheet-recorded Sleeper entries with promo-leg data from the Sleeper API.

The Google Sheet only stores PropRadar's own picks; the Sleeper-provided promo
legs (discounted lines / boosted odds) are dropped when ``saveSleeper.py`` writes
rows, even though the recorded profit/wager reflect the full parlay. This module
re-fetches recent parlays via ``my_parlays`` and matches them back to the sheet
entries so the dashboard can recover:

* the promo legs (for a correct, real parlay size / "avg legs"), and
* authoritative profit / wager values straight from the API.

Matching is best-effort: parlays older than the API window simply stay
sheet-only, and a failed/unauthorized API call leaves entries untouched so the
export never breaks.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytz

from .sheet_reader import Leg, ParlayEntry

from ..sleeper import sleepUtils
from .. import utils

# NOTE: ``getStatName`` is imported lazily inside ``normalize_parlay`` to avoid an
# import-time cycle (saveSleeper -> dashboard.export -> sleeper_enrich).

_TZ = pytz.timezone("US/Central")


def _leg_key(name: str, ou: str) -> tuple[str, str]:
    return (name.strip().lower(), (ou or "").strip().upper())


def _result_from_status(status: str) -> str:
    if status == "won":
        return "H"
    if status == "lost":
        return "M"
    return "P"


def _parlay_date(created_ms) -> date:
    epoch = created_ms / 1000
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(_TZ).date()


def normalize_parlay(entry: dict) -> dict | None:
    """Normalize a raw ``my_parlays`` entry into matchable promo/leg data.

    Returns ``None`` for parlays we can't use (no usable legs).
    """
    from ..sleeper.saveSleeper import getStatName

    try:
        created = entry["created"]
        currency_amount = float(entry["currency_amount"])
        graded_payout = float(entry["graded_payout"])
    except (KeyError, TypeError, ValueError):
        return None

    profit = graded_payout - currency_amount
    promo_type = (entry.get("display_data") or {}).get("promo_type", "")
    if promo_type == "protected_pick":
        profit = max(profit, 0.0)

    propradar_keys: set[tuple[str, str]] = set()
    promo_legs: list[Leg] = []
    total_legs = 0

    for leg in entry.get("legs", []):
        status = leg.get("status")
        line = leg.get("line") or {}
        metadata = line.get("metadata") or {}
        if status == "canceled":
            continue

        subject = line.get("subject") or {}
        name = f"{subject.get('first_name', '')} {subject.get('last_name', '')}".strip()
        ou = "O" if line.get("outcome") == "over" else "U"
        league = (line.get("sport") or "").upper()
        stat = getStatName(line.get("wager_type"))
        result = _result_from_status(status)
        try:
            payout = float(line.get("payout_multiplier"))
        except (TypeError, ValueError):
            payout = None

        total_legs += 1
        if metadata.get("promotion", "") == "true":
            promo_legs.append(
                Leg(
                    name=name,
                    league=league,
                    stat=stat,
                    ou=ou,
                    result=result,
                    payout=payout,
                    is_promo=True,
                )
            )
        else:
            propradar_keys.add(_leg_key(name, ou))

    if total_legs == 0:
        return None

    return {
        "parlay_id": entry.get("parlay_id"),
        "date": _parlay_date(created),
        "currency_amount": currency_amount,
        "profit": profit,
        "promo_type": promo_type,
        "propradar_keys": propradar_keys,
        "promo_legs": promo_legs,
        "total_legs": total_legs,
    }


def fetch_parlays() -> list[dict]:
    """Fetch and normalize completed parlays. Returns [] if unavailable."""
    try:
        raw = sleepUtils.getParlays(pending=False)
    except sleepUtils.SleeperApiError as exc:
        utils.logMsg(f"sleeper_enrich: could not fetch parlays ({exc})", debug=True, notify=False)
        return []
    except Exception as exc:  # noqa: BLE001 - never break the export
        utils.logMsg(f"sleeper_enrich: unexpected error fetching parlays ({exc})", debug=True, notify=False)
        return []

    normalized = [normalize_parlay(p) for p in raw]
    return [p for p in normalized if p is not None]


def _entry_key(entry: ParlayEntry) -> frozenset[tuple[str, str]]:
    return frozenset(_leg_key(leg.name, leg.ou) for leg in entry.legs)


def _assumed_promo_leg() -> Leg:
    """Placeholder for a promo leg we know existed but can't recover from the API.

    Result is left blank so it never feeds hit-rate, breakdowns, or Est. Edge
    (those use ``entry.legs`` only); it only contributes to the real parlay size.
    """
    return Leg(name="Promo", league="", stat="", ou="", result="", payout=None, is_promo=True)


def enrich_entries(
    entries: list[ParlayEntry],
    parlays: list[dict] | None = None,
    assume_promo_when_unmatched: bool = False,
) -> list[ParlayEntry]:
    """Attach promo legs + authoritative profit/wager to matching ``entries``.

    Matching is by parlay date plus equality of the PropRadar leg key-set
    ``{(name, O/U)}``. When multiple candidates remain, the one whose API profit
    is closest to the sheet profit wins. Each API parlay is consumed at most once.

    Entries with no API match keep their sheet data. When
    ``assume_promo_when_unmatched`` is set (Sleeper, where essentially every
    parlay is a single promo pick plus PropRadar picks), each unmatched entry
    that does not already carry a promo leg (e.g. one persisted in the sheet) is
    credited with one assumed promo leg so the real parlay size is preserved even
    for history older than the API window.
    """
    if parlays is None:
        parlays = fetch_parlays()

    by_date: dict[date, list[dict]] = {}
    for parlay in parlays:
        by_date.setdefault(parlay["date"], []).append(parlay)

    for entry in entries:
        matched = False
        candidates = by_date.get(entry.date)
        if candidates:
            key = _entry_key(entry)
            matches = [p for p in candidates if p["propradar_keys"] == key]
            if matches:
                best = min(matches, key=lambda p: abs(p["profit"] - entry.profit))
                entry.promo_legs = list(best["promo_legs"])
                entry.parlay_id = best["parlay_id"]
                entry.profit = best["profit"]
                entry.wager = best["currency_amount"]
                candidates.remove(best)
                matched = True

        # Only fall back to an assumed promo when the sheet itself has no promo
        # leg; once promos are persisted in the sheet (marker league) we must not
        # double-count by adding a placeholder on top of the real promo.
        if not matched and assume_promo_when_unmatched and not entry.promo_legs:
            entry.promo_legs = [_assumed_promo_leg()]

    return entries
