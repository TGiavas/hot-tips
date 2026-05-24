"""Per-matchup percentage calculation tests.

We exercise:

* the worked example from SPEC.md section 10 (Akrul/Bremnor / Dorga/Setti
  generalised to our real fighters), and
* the SPEC.md section 18 dataset including the "two fighter tips that cancel
  each other out" case.

Because our seeded fighters are different from the SPEC.md prose names, we use
``Corrrak`` and ``Dura`` as the "Akrul/Bremnor" pair and ``Gloz`` / ``Leo`` as
the second pair. The numeric expectations are identical.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from arena.models import DailyTipSelection
from arena.services import calculate_results


@pytest.fixture
def actor(db):
    return get_user_model().objects.create_user(
        username="seeder",
        password="x" * 16,
    )


def _activate(date_, tip, actor):
    return DailyTipSelection.objects.create(date=date_, tip=tip, submitted_by=actor)


def _result_for(results, matchup):
    return next(r for r in results if r.matchup_id == matchup.id)


def test_unmodified_matchup_is_50_50(seeded, matchups, actor):
    matchup = matchups[("Corrrak", "Dura")]
    results = calculate_results([matchup], [])
    r = results[0]
    assert r.fighter_a_percent == 50
    assert r.fighter_b_percent == 50


def test_spec_section_10_example(seeded, matchups, tips, actor):
    """Reproduce the SPEC.md section 10 worked example exactly.

    Active tips for Corrrak vs Dura:

        Corrrak +5%
        Dura -5%
        Corrrak +10% vs Dura

    Expected: Corrrak 70 / Dura 30.
    """
    import datetime

    matchup = matchups[("Corrrak", "Dura")]
    today = datetime.date(2026, 5, 24)

    _activate(today, tips["Corrrak +5%"], actor)
    _activate(today, tips["Dura -5%"], actor)
    _activate(today, tips["Corrrak +10% vs Dura"], actor)

    selections = list(
        DailyTipSelection.objects.select_related(
            "tip__fighter",
            "tip__matchup__fighter_a",
            "tip__matchup__fighter_b",
            "tip__target_fighter",
        ).filter(date=today)
    )

    [result] = calculate_results([matchup], selections)
    assert result.fighter_a == "Corrrak"
    assert result.fighter_a_percent == 70
    assert result.fighter_b == "Dura"
    assert result.fighter_b_percent == 30


def test_spec_section_18_canceling_fighter_tips(seeded, matchups, tips, actor):
    """Reproduce the section-18 case where two fighter tips on opposite
    fighters cancel out."""
    import datetime

    matchup = matchups[("Gloz", "Leo")]
    today = datetime.date(2026, 5, 24)

    _activate(today, tips["Gloz +5%"], actor)
    _activate(today, tips["Leo +5%"], actor)

    selections = list(
        DailyTipSelection.objects.select_related(
            "tip__fighter",
            "tip__matchup__fighter_a",
            "tip__matchup__fighter_b",
            "tip__target_fighter",
        ).filter(date=today)
    )
    [result] = calculate_results([matchup], selections)
    assert result.fighter_a_percent == 50
    assert result.fighter_b_percent == 50


def test_fighter_tip_applies_to_every_matchup_with_that_fighter(
    seeded, matchups, tips, actor
):
    """A single fighter-wide +5% must shift every matchup containing the
    fighter, not just one row."""
    import datetime

    today = datetime.date(2026, 5, 24)
    _activate(today, tips["Corrrak +5%"], actor)

    selections = list(
        DailyTipSelection.objects.select_related(
            "tip__fighter",
            "tip__matchup__fighter_a",
            "tip__matchup__fighter_b",
            "tip__target_fighter",
        ).filter(date=today)
    )

    from arena.models import Matchup

    all_matchups = list(
        Matchup.objects.select_related("fighter_a", "fighter_b").all()
    )
    results = calculate_results(all_matchups, selections)

    corrrak_matchup_count = 0
    for m, r in zip(all_matchups, results):
        if m.fighter_a.name == "Corrrak":
            assert r.fighter_a_percent == 55
            corrrak_matchup_count += 1
        elif m.fighter_b.name == "Corrrak":
            assert r.fighter_b_percent == 55
            corrrak_matchup_count += 1
        else:
            assert r.fighter_a_percent == 50
    # Corrrak is in 6 of the 21 matchups.
    assert corrrak_matchup_count == 6


def test_clamp_floors_at_zero(seeded, matchups, tips, actor):
    """If extreme stacked tips would push a fighter below 0, clamp to 0."""
    import datetime

    today = datetime.date(2026, 5, 24)
    matchup = matchups[("Corrrak", "Dura")]

    # Stack everything against Dura: Dura -5, Corrrak +5, Corrrak +10 vs Dura.
    # That's 50 + 5 + 5 + 10 = 70. Then add more matchup tips? There's only
    # one Corrrak-+10 tip per direction, so we can't push past 70 via the
    # seeded definitions. Construct a synthetic extra tip to test clamping.
    from arena.models import TipDefinition

    extra = TipDefinition.objects.create(
        label="Synthetic Corrrak +200% vs Dura",
        tip_type=TipDefinition.TipType.MATCHUP,
        matchup=matchup,
        target_fighter=matchup.fighter_a,
        modifier=200,
    )
    _activate(today, extra, actor)

    selections = list(
        DailyTipSelection.objects.select_related(
            "tip__fighter",
            "tip__matchup__fighter_a",
            "tip__matchup__fighter_b",
            "tip__target_fighter",
        ).filter(date=today)
    )
    [result] = calculate_results([matchup], selections)
    assert result.fighter_a_percent == 100
    assert result.fighter_b_percent == 0
