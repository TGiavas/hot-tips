"""Serialization helpers for the arena API.

The response shape is custom (see SPEC.md section 12.1) so we avoid DRF's
``ModelSerializer`` machinery and just build plain dicts from ORM instances.
This keeps the rendered JSON predictable and easy to type on the frontend.
"""
from __future__ import annotations

from typing import Iterable

from .models import (
    DAILY_TIP_CAP,
    DailyTipSelection,
    Matchup,
    SpreadsheetSyncConfig,
    TipDefinition,
)
from .services import (
    MatchResult,
    calculate_results,
    selection_submitter_display,
)


def serialize_tip_definition(tip: TipDefinition) -> dict:
    return {
        "tip_id": tip.id,
        "label": tip.label,
        "tip_type": tip.tip_type,
        "fighter_id": tip.fighter_id,
        "matchup_id": tip.matchup_id,
        "target_fighter_id": tip.target_fighter_id,
        "modifier": tip.modifier,
        "sort_order": tip.sort_order,
    }


def serialize_active_tip(selection: DailyTipSelection) -> dict:
    return {
        "tip_id": selection.tip_id,
        "submitted_by": {
            "id": selection.submitted_by_id,
            "display_name": selection_submitter_display(selection),
            # Flag rows that came from the spreadsheet so the frontend can
            # style them differently if it wants to (e.g. dim icon).
            "from_spreadsheet": bool(selection.external_submitter_name),
        },
    }


def serialize_sync_status(config: SpreadsheetSyncConfig) -> dict:
    """Compact view of the spreadsheet-sync state for the header indicator.

    Kept terse on purpose — the React header just needs to know "is it
    healthy, when did it last run, and what does the tooltip say".
    """
    return {
        "enabled": config.enabled,
        "configured": bool(config.share_url),
        "status": config.last_status,
        "message": config.last_message,
        "last_run_at": (
            config.last_run_at.isoformat() if config.last_run_at else None
        ),
        "last_sheet_date": (
            config.last_sheet_date.isoformat()
            if config.last_sheet_date
            else None
        ),
        "last_added_count": config.last_added_count,
        "last_skipped_count": config.last_skipped_count,
    }


def serialize_matchup(matchup: Matchup) -> dict:
    return {
        "matchup_id": matchup.id,
        "fighter_a": {"id": matchup.fighter_a_id, "name": matchup.fighter_a.name},
        "fighter_b": {"id": matchup.fighter_b_id, "name": matchup.fighter_b.name},
        "sort_order": matchup.sort_order,
    }


def serialize_fighter_tip(tip: TipDefinition) -> dict:
    return {
        **serialize_tip_definition(tip),
        "fighter_name": tip.fighter.name if tip.fighter_id else None,
    }


def serialize_matchup_tip(tip: TipDefinition) -> dict:
    return {
        **serialize_tip_definition(tip),
        "matchup_label": str(tip.matchup) if tip.matchup_id else None,
        "target_fighter_name": tip.target_fighter.name,
    }


def build_arena_state(
    game_day,
    fighters,
    matchups: Iterable[Matchup],
    fighter_tips: Iterable[TipDefinition],
    matchup_tips: Iterable[TipDefinition],
    selections: Iterable[DailyTipSelection],
    sync_config: SpreadsheetSyncConfig | None = None,
) -> dict:
    matchups = list(matchups)
    selections = list(selections)
    results: list[MatchResult] = calculate_results(matchups, selections)

    return {
        "game_day": game_day.isoformat(),
        "known_tip_count": len(selections),
        "max_tips": DAILY_TIP_CAP,
        "fighters": [
            {"id": f.id, "name": f.name, "sort_order": f.sort_order}
            for f in fighters
        ],
        "matchups": [serialize_matchup(m) for m in matchups],
        "fighter_tips": [serialize_fighter_tip(t) for t in fighter_tips],
        "matchup_tips": [serialize_matchup_tip(t) for t in matchup_tips],
        "active_tips": [serialize_active_tip(s) for s in selections],
        "match_results": [r.to_dict() for r in results],
        "sync_status": (
            serialize_sync_status(sync_config) if sync_config else None
        ),
    }
