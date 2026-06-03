"""Arena API views.

Three main endpoints:

* ``GET /api/arena/state/`` returns the full arena state for *today* (game
  day is computed server-side in ``America/New_York``).
* ``POST /api/arena/tips/toggle/`` toggles one tip in the shared daily pool,
  writes an audit log row, and returns the new arena state.
* ``POST /api/arena/sync/`` manually triggers a community-spreadsheet sync
  (auth-gated; see :mod:`arena.sync`).

Plus a couple of trivial auth helpers used by the React client:

* ``GET /api/auth/csrf/``    no-op view that sets the CSRF cookie.
* ``GET /api/auth/whoami/``  returns the current user or 401.

Auto-sync: ``GET /api/arena/state/`` opportunistically runs a sync if it's
been more than :data:`AUTO_SYNC_INTERVAL_SECONDS` since the last attempt
and the config is enabled / has a URL. This piggybacks on the React
client's 10-second polling so the spreadsheet stays fresh without
provisioning a separate scheduler (which our SQLite-per-machine deploy
can't easily share with the web process anyway).
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import connection, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    DAILY_TIP_CAP,
    DailyTipAuditLog,
    DailyTipSelection,
    Fighter,
    Matchup,
    SpreadsheetSyncConfig,
    TipDefinition,
)
from .serializers import build_arena_state
from .services import current_game_day, display_name


log = logging.getLogger(__name__)

# How often the in-request auto-sync hook is allowed to actually fire.
# Lower values are wasted load on OneDrive; higher values let the
# spreadsheet drift further before the page reflects it.
AUTO_SYNC_INTERVAL_SECONDS = 5 * 60


def _load_state_payload(game_day) -> dict:
    fighters = list(Fighter.objects.filter(is_active=True))
    matchups = list(
        Matchup.objects.filter(is_active=True)
        .select_related("fighter_a", "fighter_b")
    )
    tip_definitions = list(
        TipDefinition.objects.filter(is_active=True)
        .select_related("fighter", "matchup__fighter_a", "matchup__fighter_b", "target_fighter")
    )
    fighter_tips = [
        t for t in tip_definitions if t.tip_type == TipDefinition.TipType.FIGHTER
    ]
    matchup_tips = [
        t for t in tip_definitions if t.tip_type == TipDefinition.TipType.MATCHUP
    ]
    selections = list(
        DailyTipSelection.objects.filter(date=game_day)
        .select_related(
            "tip__fighter",
            "tip__matchup__fighter_a",
            "tip__matchup__fighter_b",
            "tip__target_fighter",
            "submitted_by",
        )
    )
    sync_config = SpreadsheetSyncConfig.get_solo()
    return build_arena_state(
        game_day=game_day,
        fighters=fighters,
        matchups=matchups,
        fighter_tips=fighter_tips,
        matchup_tips=matchup_tips,
        selections=selections,
        sync_config=sync_config,
    )


def _maybe_auto_sync() -> None:
    """If due, run one community-spreadsheet sync inline.

    Best-effort: any failure is swallowed and logged. The result is written
    into ``SpreadsheetSyncConfig`` regardless, so the next state response
    will surface the error in ``sync_status``.

    Runs only when:
    * sync is enabled and the share URL is configured,
    * no run has happened in the last :data:`AUTO_SYNC_INTERVAL_SECONDS`.
    """
    try:
        config = SpreadsheetSyncConfig.get_solo()
    except Exception:  # pragma: no cover - DB issue, let view return state
        log.exception("could not load SpreadsheetSyncConfig for auto-sync")
        return
    if not (config.enabled and config.share_url):
        return
    if config.last_run_at is not None:
        elapsed = timezone.now() - config.last_run_at
        if elapsed < timedelta(seconds=AUTO_SYNC_INTERVAL_SECONDS):
            return
    # Import locally to keep the views module light and skip the
    # ``openpyxl`` import when sync isn't actually triggered.
    from .sync import sync_spreadsheet_once

    try:
        sync_spreadsheet_once()
    except Exception:  # pragma: no cover - belt-and-braces
        log.exception("auto-sync raised; continuing with stale state")


class ArenaStateView(APIView):
    """Return the full arena state for today's game day.

    Read-only for everyone (anonymous viewers welcome). Editing requires
    authentication and goes through :class:`ToggleTipView`. Also acts as
    the auto-sync trigger — see :func:`_maybe_auto_sync`.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        _maybe_auto_sync()
        game_day = current_game_day()
        return Response(_load_state_payload(game_day))


class TriggerSpreadsheetSyncView(APIView):
    """Force one community-spreadsheet sync cycle right now.

    Authenticated users only — same gate as :class:`ToggleTipView`. We
    always run with ``force=True`` so an admin can troubleshoot even if
    they've set ``enabled=False`` in admin, but the date gate still
    protects against applying a stale sheet.

    Returns the full updated arena state on success, including the new
    ``sync_status`` block so the header indicator updates immediately.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .sync import sync_spreadsheet_once

        sync_spreadsheet_once(force=True)
        game_day = current_game_day()
        return Response(_load_state_payload(game_day))


class ToggleTipView(APIView):
    """Activate or deactivate a single tip in the shared daily pool.

    The request body needs only ``{"tip_id": <int>}``. The server always
    operates on today's game day in ``America/New_York`` (SPEC.md section 5).

    Behaviour:

    * if the tip is currently active for today, delete the row + audit
      ``deactivate``;
    * else if the pool already has ``DAILY_TIP_CAP`` (15) tips active, return
      ``409 Conflict``;
    * else create the row + audit ``activate``.

    The whole operation runs in ``transaction.atomic()`` with
    ``select_for_update()`` over *all* of today's selections (not just the
    row for this tip — that would lock nothing when activating a fresh tip
    and let two concurrent activations both pass the cap check). On
    Postgres this acquires row-level locks on every active selection for
    today. On SQLite ``select_for_update`` is unsupported but
    ``transaction.atomic`` serialises writes at the DB-file level, so the
    cap stays honest there too.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tip_id = request.data.get("tip_id")
        if not isinstance(tip_id, int):
            return Response(
                {"detail": "tip_id (int) required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tip = TipDefinition.objects.get(pk=tip_id, is_active=True)
        except TipDefinition.DoesNotExist:
            return Response(
                {"detail": "Unknown tip."},
                status=status.HTTP_404_NOT_FOUND,
            )

        game_day = current_game_day()

        with transaction.atomic():
            base_qs = DailyTipSelection.objects.filter(date=game_day)
            if connection.features.has_select_for_update:
                base_qs = base_qs.select_for_update()
            # Materialise the full day's rows in one query: this both locks
            # them (on Postgres) and gives us a consistent view to derive
            # `existing_for_tip` and `current_count` from. Filtering the
            # queryset *after* this is essentially free — at most 15 rows.
            todays_selections = list(base_qs)
            existing_for_tip = [
                s for s in todays_selections if s.tip_id == tip.id
            ]
            current_count = len(todays_selections)

            if existing_for_tip:
                existing_for_tip[0].delete()
                DailyTipAuditLog.objects.create(
                    date=game_day,
                    tip=tip,
                    action=DailyTipAuditLog.Action.DEACTIVATE,
                    actor=request.user,
                )
            else:
                if current_count >= DAILY_TIP_CAP:
                    return Response(
                        {"detail": "shared daily pool full"},
                        status=status.HTTP_409_CONFLICT,
                    )
                DailyTipSelection.objects.create(
                    date=game_day,
                    tip=tip,
                    submitted_by=request.user,
                )
                DailyTipAuditLog.objects.create(
                    date=game_day,
                    tip=tip,
                    action=DailyTipAuditLog.Action.ACTIVATE,
                    actor=request.user,
                )

        return Response(_load_state_payload(game_day))


@ensure_csrf_cookie
@require_GET
def csrf_view(request):
    """No-op endpoint that ensures the CSRF cookie is set on the response."""
    return JsonResponse({"detail": "csrf cookie set"})


class WhoAmIView(APIView):
    """Return the current user or 401.

    Implemented as a DRF view (rather than a plain Django function) so that
    DRF authentication classes drive ``request.user`` — this lets the test
    suite use ``APIClient.force_authenticate`` against this endpoint.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "not authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user = request.user
        return Response(
            {
                "id": user.id,
                "username": user.get_username(),
                "display_name": display_name(user),
                "is_staff": user.is_staff,
            }
        )
