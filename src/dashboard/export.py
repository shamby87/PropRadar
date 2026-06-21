"""Build and export the PropRadar dashboard JSON payload.

Reads both platform worksheets, computes per-platform and combined analytics,
and writes a single JSON file consumed by the static site in ``docs/``.

Run standalone with:  ``python -m src.dashboard.export``
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from . import config
from . import sheet_reader
from . import sleeper_enrich
from . import stats


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def build_dashboard_data(client=None) -> dict:
    """Read both platforms and assemble the full dashboard payload."""
    client = client or sheet_reader.get_gspread_client()

    sleeper_entries, sleeper_summaries = sheet_reader.read_sleeper_performance(client)
    sleeper_entries = sleeper_enrich.enrich_entries(
        sleeper_entries, assume_promo_when_unmatched=config.ASSUME_SLEEPER_PROMO_LEG
    )
    pp_entries, pp_summaries = sheet_reader.read_prizepicks_performance(client)
    combined = sleeper_entries + pp_entries

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "site_title": config.SITE_TITLE,
        "site_tagline": config.SITE_TAGLINE,
        "baseline_odds": config.FAIR_ODDS_BASELINE,
        "platforms": {
            "overall": stats.compute_platform_stats(
                combined, default_wager=config.DEFAULT_SLEEPER_WAGER
            ),
            "sleeper": stats.compute_platform_stats(
                sleeper_entries, sleeper_summaries, default_wager=config.DEFAULT_SLEEPER_WAGER
            ),
            "prizepicks": stats.compute_platform_stats(pp_entries, pp_summaries),
        },
    }


def export_to_json(data: dict, path: str | None = None) -> str:
    """Write ``data`` as pretty JSON to ``path`` (default from config)."""
    if path is None:
        path = os.path.join(_repo_root(), config.DEFAULT_OUTPUT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    return path


def export_all(path: str | None = None, client=None) -> str | None:
    """Build and write the dashboard payload.

    Honors the ``DASHBOARD_EXPORT`` env var: set it to ``0`` to skip (useful when
    called automatically from the save scripts). Failures are swallowed with a
    message so they never break the recording workflow.
    """
    if os.environ.get("DASHBOARD_EXPORT", "1") == "0":
        return None
    try:
        data = build_dashboard_data(client)
        out_path = export_to_json(data, path)
        print(f"dashboard: exported stats to {out_path}")
        return out_path
    except Exception as exc:  # noqa: BLE001 - never break the save workflow
        print(f"dashboard: export failed ({exc})")
        return None


if __name__ == "__main__":
    export_all()
