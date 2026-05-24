"""Game-day rollover tests.

The game day rolls over at midnight ``America/New_York`` wall-clock. These
tests pin "now" to specific UTC instants around midnight in NY, on both
standard time (EST = UTC-5) and daylight saving time (EDT = UTC-4), and
verify ``current_game_day`` returns the expected NY-local date.
"""
from __future__ import annotations

from datetime import date

import time_machine

from arena.services import current_game_day


def test_standard_time_just_before_midnight_ny():
    # EST = UTC-5. 04:59 UTC on Jan 16 == 23:59 NY on Jan 15.
    with time_machine.travel("2026-01-16T04:59:00Z", tick=False):
        assert current_game_day() == date(2026, 1, 15)


def test_standard_time_just_after_midnight_ny():
    # 05:00 UTC on Jan 16 == 00:00 NY on Jan 16.
    with time_machine.travel("2026-01-16T05:00:00Z", tick=False):
        assert current_game_day() == date(2026, 1, 16)


def test_daylight_time_just_before_midnight_ny():
    # EDT = UTC-4. 03:59 UTC on June 16 == 23:59 NY on June 15.
    with time_machine.travel("2026-06-16T03:59:00Z", tick=False):
        assert current_game_day() == date(2026, 6, 15)


def test_daylight_time_just_after_midnight_ny():
    # 04:00 UTC on June 16 == 00:00 NY on June 16.
    with time_machine.travel("2026-06-16T04:00:00Z", tick=False):
        assert current_game_day() == date(2026, 6, 16)


def test_dst_spring_forward_day():
    # Spring forward 2026: DST begins at 02:00 local on Sun Mar 8.
    # 06:30 UTC on Mar 8 -> 02:30 EDT (a "valid" local time after the jump).
    with time_machine.travel("2026-03-08T06:30:00Z", tick=False):
        assert current_game_day() == date(2026, 3, 8)


def test_dst_fall_back_day():
    # Fall back 2026: DST ends at 02:00 local on Sun Nov 1.
    # 05:30 UTC on Nov 1 -> 01:30 EDT (the "first" 01:30, before the fold).
    with time_machine.travel("2026-11-01T05:30:00Z", tick=False):
        assert current_game_day() == date(2026, 11, 1)
    # 06:30 UTC on Nov 1 -> 01:30 EST (the "second" 01:30, after the fold).
    with time_machine.travel("2026-11-01T06:30:00Z", tick=False):
        assert current_game_day() == date(2026, 11, 1)
