"""Domain logic shared between views, the seed command, and tests.

* :func:`current_game_day` computes the current game day in
  ``America/New_York`` wall-clock terms (DST-aware), per SPEC.md section 1.
* :func:`calculate_results` implements the per-matchup percentage formula from
  SPEC.md section 10.
* :func:`display_name` resolves a user to the string shown next to their
  submitted tips.
* :func:`selection_submitter_display` resolves a ``DailyTipSelection`` to the
  string the UI shows: either the human user's display name, or
  ``"<name> (Spreadsheet)"`` for sync-imported rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from zoneinfo import ZoneInfo

from django.utils import timezone

from .models import (
    SPREADSHEET_SYNC_USERNAME,
    DailyTipSelection,
    Matchup,
    TipDefinition,
)


GAME_TZ = ZoneInfo("America/New_York")
START_PERCENT = 50

# Suffix appended to sheet-imported submitter names so the UI can visually
# distinguish "Aleks (manual)" from "Aleks (Spreadsheet)" at a glance.
SPREADSHEET_SUBMITTER_SUFFIX = " (Spreadsheet)"


def current_game_day() -> date:
    """Return today's game day as a ``date``.

    The game day rolls over at midnight ``America/New_York`` wall-clock,
    irrespective of the server's local timezone.
    """
    return timezone.now().astimezone(GAME_TZ).date()


def display_name(user) -> str:
    """Return the public display name for ``user`` (full name or username)."""
    if user is None:
        return ""
    full = user.get_full_name() if hasattr(user, "get_full_name") else ""
    return full.strip() or user.get_username()


def selection_submitter_display(selection: DailyTipSelection) -> str:
    """Return the string the UI shows for a tip's submitter.

    * Manual rows (clicked by a real signed-in user) -> that user's
      :func:`display_name`.
    * Sync rows (owned by the ``spreadsheet-sync`` system user) ->
      ``"<external name> (Spreadsheet)"`` so contributors keep credit
      without us having to mint a Django account per sheet author.

    Falls back to plain :func:`display_name` if a sync row somehow has no
    ``external_submitter_name`` (e.g. a manual admin edit).
    """
    user = selection.submitted_by
    is_sync_user = (
        user is not None
        and user.get_username() == SPREADSHEET_SYNC_USERNAME
    )
    external = (selection.external_submitter_name or "").strip()
    if is_sync_user and external:
        return f"{external}{SPREADSHEET_SUBMITTER_SUFFIX}"
    if is_sync_user:
        # No external name recorded — surface something legible rather than
        # the literal username slug.
        return f"Anonymous{SPREADSHEET_SUBMITTER_SUFFIX}"
    return display_name(user)


@dataclass(frozen=True)
class MatchResult:
    matchup_id: int
    fighter_a: str
    fighter_a_percent: int
    fighter_b: str
    fighter_b_percent: int

    def to_dict(self) -> dict:
        return {
            "matchup_id": self.matchup_id,
            "fighter_a": self.fighter_a,
            "fighter_a_percent": self.fighter_a_percent,
            "fighter_b": self.fighter_b,
            "fighter_b_percent": self.fighter_b_percent,
        }


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def calculate_results(
    matchups: Iterable[Matchup],
    selections: Iterable[DailyTipSelection],
) -> list[MatchResult]:
    """Compute per-matchup percentages using the active shared tip selections.

    Implements SPEC.md section 10:

    * each matchup starts at 50/50
    * for each active tip that applies to a matchup, add its ``modifier`` to
      the tip's ``target_fighter`` (and subtract the same amount from the
      opponent, which falls out of ``b = 100 - a``)
    * clamp Fighter A's percent to ``[0, 100]``

    The function is pure: it does not hit the database, it operates over the
    iterables it's given. Callers are expected to have eagerly loaded
    ``tip.fighter``, ``tip.matchup``, and ``tip.target_fighter`` (via
    ``select_related``) for efficiency, but the function itself doesn't care.
    """
    matchups = list(matchups)
    selections = list(selections)

    results: list[MatchResult] = []
    for matchup in matchups:
        fighter_a_percent = START_PERCENT
        for selection in selections:
            tip = selection.tip
            if not _tip_applies(tip, matchup):
                continue
            if tip.target_fighter_id == matchup.fighter_a_id:
                fighter_a_percent += tip.modifier
            elif tip.target_fighter_id == matchup.fighter_b_id:
                fighter_a_percent -= tip.modifier
        fighter_a_percent = _clamp(fighter_a_percent, 0, 100)
        results.append(
            MatchResult(
                matchup_id=matchup.id,
                fighter_a=matchup.fighter_a.name,
                fighter_a_percent=fighter_a_percent,
                fighter_b=matchup.fighter_b.name,
                fighter_b_percent=100 - fighter_a_percent,
            )
        )
    return results


def _tip_applies(tip: TipDefinition, matchup: Matchup) -> bool:
    if tip.tip_type == TipDefinition.TipType.MATCHUP:
        return tip.matchup_id == matchup.id
    # Fighter-wide tip: applies to every matchup that contains the fighter.
    return tip.fighter_id in (matchup.fighter_a_id, matchup.fighter_b_id)
