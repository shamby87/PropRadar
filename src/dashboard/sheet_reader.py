"""Read PropRadar performance rows from Google Sheets into typed entries.

The Google Sheets access mirrors the auth used by ``saveSleeper.py`` /
``savePP.py``. The row-parsing logic (:func:`parse_rows`) is kept pure so it can
be unit tested without any network access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import os
import re

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from . import config

_SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "googlesheets-credentials.json"
)


@dataclass
class Leg:
    """A single pick within a parlay/entry."""

    name: str
    league: str
    stat: str
    ou: str
    result: str
    payout: float | None = None
    is_promo: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "league": self.league,
            "stat": self.stat,
            "ou": self.ou,
            "result": self.result,
            "payout": self.payout,
            "is_promo": self.is_promo,
        }


@dataclass
class ParlayEntry:
    """A settled parlay/entry: a group of legs with one parlay-level profit.

    ``legs`` holds only PropRadar's own picks (as read from the sheet) so that
    skill metrics stay PropRadar-scoped. ``promo_legs`` holds Sleeper-provided
    promo picks (from the sheet or an assumed placeholder for older entries);
    they are excluded from hit-rate/breakdowns but counted toward avg legs.
    """

    platform: str
    date: date
    profit: float
    legs: list[Leg] = field(default_factory=list)
    wager: float | None = None
    promo_legs: list[Leg] = field(default_factory=list)
    parlay_id: str | None = None

    @property
    def outcome(self) -> str:
        if self.profit > 0:
            return "win"
        if self.profit < 0:
            return "loss"
        return "push"

    @property
    def total_legs(self) -> int:
        return len(self.legs) + len(self.promo_legs)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "date": self.date.strftime("%m/%d/%y"),
            "iso_date": self.date.isoformat(),
            "profit": round(self.profit, 2),
            "wager": None if self.wager is None else round(self.wager, 2),
            "outcome": self.outcome,
            "legs": [leg.to_dict() for leg in self.legs],
            "promo_legs": [leg.to_dict() for leg in self.promo_legs],
            "total_legs": self.total_legs,
            "parlay_id": self.parlay_id,
        }


def _parse_float(value: str) -> float | None:
    text = (value or "").strip().replace("$", "").replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if text == "" or text.lower() == "date":
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if match:
        month, day, year = (int(match.group(i)) for i in range(1, 4))
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _col(row: list[str], index_1based: int) -> str:
    idx = index_1based - 1
    return row[idx] if idx < len(row) else ""


def _is_leg_row(row: list[str]) -> bool:
    entry_date = _parse_date(_col(row, config.COL_DATE))
    result = (_col(row, config.COL_RESULT) or "").strip().upper()
    name = (_col(row, config.COL_PLAYER) or "").strip()
    return entry_date is not None and name != "" and result in config.VALID_RESULTS


def _flush_group(
    platform: str,
    legs: list[Leg],
    meta: list[dict],
    entries: list[ParlayEntry],
) -> None:
    """Finalize a consecutive run of leg rows into one parlay entry."""
    if not legs:
        return
    profit = None
    wager = None
    for row_meta in reversed(meta):
        if row_meta["profit"] is not None:
            profit = row_meta["profit"]
            wager = row_meta["wager"]
            break
    if profit is None:
        return
    propradar_legs = [leg for leg in legs if not leg.is_promo]
    promo_legs = [leg for leg in legs if leg.is_promo]
    entries.append(
        ParlayEntry(
            platform=platform,
            date=meta[0]["date"],
            profit=profit,
            legs=propradar_legs,
            wager=wager,
            promo_legs=promo_legs,
        )
    )


def parse_rows(rows: list[list[str]], platform: str) -> list[ParlayEntry]:
    """Group raw worksheet rows into :class:`ParlayEntry` objects.

    ``rows`` is a list of full rows (1-based columns mapped to 0-based indexes).
    Consecutive leg rows (date + player + H/M/P result) form one parlay. Profit
    in column I usually appears on the final leg; when multiple legs in a group
    have profit values, the last one wins. Blank separator rows end a group.
    """
    entries: list[ParlayEntry] = []
    pending_legs: list[Leg] = []
    pending_meta: list[dict] = []

    for row in rows:
        if not _is_leg_row(row):
            _flush_group(platform, pending_legs, pending_meta, entries)
            pending_legs = []
            pending_meta = []
            continue

        result = (_col(row, config.COL_RESULT) or "").strip().upper()
        profit_raw = (_col(row, config.COL_PROFIT) or "").strip()
        profit = _parse_float(profit_raw) if profit_raw else None
        league = (_col(row, config.COL_LEAGUE) or "").strip().upper()
        pending_legs.append(
            Leg(
                name=(_col(row, config.COL_PLAYER) or "").strip(),
                league=league,
                stat=(_col(row, config.COL_STAT) or "").strip(),
                ou=(_col(row, config.COL_OU) or "").strip().upper(),
                result=result,
                payout=_parse_float(_col(row, config.COL_PAYOUT)),
                is_promo=league in config.PROMO_LEAGUE_MARKERS,
            )
        )
        pending_meta.append(
            {
                "date": _parse_date(_col(row, config.COL_DATE)),
                "profit": profit,
                "wager": _parse_float(_col(row, config.COL_WAGER)),
            }
        )

    _flush_group(platform, pending_legs, pending_meta, entries)
    return entries


def get_gspread_client() -> gspread.Client:
    """Authorize a gspread client using the shared service-account credentials."""
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        os.path.abspath(_CREDENTIALS_PATH), _SCOPE
    )
    return gspread.authorize(credentials)


def read_summary_cells(worksheet, cell_map: dict[str, str]) -> dict[str, str]:
    """Read configured formula/summary cells verbatim for cross-checking."""
    summaries: dict[str, str] = {}
    for label, cell in cell_map.items():
        try:
            summaries[label] = worksheet.acell(cell).value
        except Exception:
            summaries[label] = None
    return summaries


def read_platform(client: gspread.Client, worksheet_name: str, platform: str,
                  summary_cells: dict[str, str]):
    """Read one platform worksheet, returning (entries, summaries)."""
    worksheet = client.open(config.WORKBOOK_NAME).worksheet(worksheet_name)
    rows = worksheet.get_all_values()
    entries = parse_rows(rows, platform)
    summaries = read_summary_cells(worksheet, summary_cells) if summary_cells else {}
    return entries, summaries


def read_sleeper_performance(client: gspread.Client | None = None):
    client = client or get_gspread_client()
    entries, summaries = read_platform(
        client, config.SLEEPER_WORKSHEET, "sleeper", config.SLEEPER_SUMMARY_CELLS
    )
    return apply_assumed_sleeper_promos(entries), summaries


def _assumed_promo_leg() -> Leg:
    """Placeholder for a Sleeper promo leg known to have existed but not recorded."""
    return Leg(name="Promo", league="", stat="", ou="", result="", payout=None, is_promo=True)


def apply_assumed_sleeper_promos(
    entries: list[ParlayEntry],
    *,
    enabled: bool | None = None,
) -> list[ParlayEntry]:
    """Credit one assumed promo leg on Sleeper entries that do not already have one.

    Older sheet rows omit the Sleeper-provided promo pick. The placeholder only
    affects avg legs; hit-rate, breakdowns, and Est. Edge use ``entry.legs`` only.
    """
    if enabled is None:
        enabled = config.ASSUME_SLEEPER_PROMO_LEG
    if not enabled:
        return entries

    for entry in entries:
        if not entry.promo_legs:
            entry.promo_legs = [_assumed_promo_leg()]

    return entries


def read_prizepicks_performance(client: gspread.Client | None = None):
    client = client or get_gspread_client()
    return read_platform(
        client, config.PRIZEPICKS_WORKSHEET, "prizepicks", config.PRIZEPICKS_SUMMARY_CELLS
    )
