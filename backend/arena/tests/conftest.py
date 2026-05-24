"""Shared pytest fixtures for the arena tests.

The ``seeded`` fixture invokes the same ``seed_arena`` management command the
operator runs in production, so the tests exercise the real seed path and
prove it's idempotent.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from arena.models import Fighter, Matchup, TipDefinition


@pytest.fixture
def seeded(db) -> None:
    call_command("seed_arena")


@pytest.fixture
def user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="alice",
        password="secret-pw-123!xyz",
        first_name="Alice",
    )


@pytest.fixture
def fighters(seeded) -> dict[str, Fighter]:
    return {f.name: f for f in Fighter.objects.all()}


@pytest.fixture
def matchups(seeded) -> dict[tuple[str, str], Matchup]:
    return {
        (m.fighter_a.name, m.fighter_b.name): m
        for m in Matchup.objects.select_related("fighter_a", "fighter_b")
    }


@pytest.fixture
def tips(seeded) -> dict[str, TipDefinition]:
    return {t.label: t for t in TipDefinition.objects.all()}
