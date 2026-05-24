"""Arena API views.

Two main endpoints:

* ``GET /api/arena/state/`` returns the full arena state for *today* (game
  day is computed server-side in ``America/New_York``).
* ``POST /api/arena/tips/toggle/`` toggles one tip in the shared daily pool,
  writes an audit log row, and returns the new arena state.

Plus a couple of trivial auth helpers used by the React client:

* ``GET /api/auth/csrf/``    no-op view that sets the CSRF cookie.
* ``GET /api/auth/whoami/``  returns the current user or 401.
"""
from __future__ import annotations

from django.db import connection, transaction
from django.http import JsonResponse
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
    TipDefinition,
)
from .serializers import build_arena_state
from .services import current_game_day, display_name


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
    return build_arena_state(
        game_day=game_day,
        fighters=fighters,
        matchups=matchups,
        fighter_tips=fighter_tips,
        matchup_tips=matchup_tips,
        selections=selections,
    )


class ArenaStateView(APIView):
    """Return the full arena state for today's game day.

    Read-only for everyone (anonymous viewers welcome). Editing requires
    authentication and goes through :class:`ToggleTipView`.
    """

    permission_classes = [AllowAny]

    def get(self, request):
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
    ``select_for_update()`` over today's selections, so concurrent toggles
    can't push the pool past 15.
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
            # SQLite doesn't support row-level SELECT ... FOR UPDATE. Django's
            # transaction.atomic() already serialises writes there, so we only
            # add explicit row-locking when the backend supports it.
            base_qs = DailyTipSelection.objects.filter(date=game_day)
            if connection.features.has_select_for_update:
                base_qs = base_qs.select_for_update()
            existing_for_tip = list(base_qs.filter(tip=tip))
            current_count = base_qs.count()

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
