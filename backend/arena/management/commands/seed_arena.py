"""Seed the static arena data: fighters, matchups, and tip definitions.

Idempotent: run as many times as you like; nothing duplicates. Existing rows
keep their ``is_active``, ``sort_order``, and any other manual edits unless
``--reset`` is passed.

Fighters and matchups come from SPEC.md's "21 pairings of 7 fighters" decision
locked during planning. Tip definitions are auto-derived:

* For each fighter: ``"<Name> +5%"`` (modifier=+5) and ``"<Name> -5%"`` (-5).
* For each matchup ``(A, B)``: ``"<A> +10% vs <B>"`` and ``"<B> +10% vs <A>"``,
  both ``modifier=+10`` with the correct ``target_fighter``.
"""
from __future__ import annotations

from itertools import combinations

from django.core.management.base import BaseCommand
from django.db import transaction

from arena.models import Fighter, Matchup, TipDefinition


FIGHTER_NAMES = [
    "Corrrak",
    "Dura",
    "Gloz",
    "Leo",
    "Otis",
    "Ushug",
    "Viz",
]


class Command(BaseCommand):
    help = "Seed/refresh the static arena data (fighters, matchups, tip definitions)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Delete all existing seed rows (fighters, matchups, tip "
                "definitions) before re-creating them. Will fail if any "
                "DailyTipSelection or DailyTipAuditLog rows reference them."
            ),
        )

    @transaction.atomic
    def handle(self, *args, reset: bool = False, **options) -> None:
        if reset:
            TipDefinition.objects.all().delete()
            Matchup.objects.all().delete()
            Fighter.objects.all().delete()

        fighters = self._seed_fighters()
        matchups = self._seed_matchups(fighters)
        self._seed_fighter_tips(fighters)
        self._seed_matchup_tips(matchups)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(fighters)} fighters, {len(matchups)} matchups, "
                f"{TipDefinition.objects.count()} tip definitions."
            )
        )

    def _seed_fighters(self) -> dict[str, Fighter]:
        fighters: dict[str, Fighter] = {}
        for index, name in enumerate(FIGHTER_NAMES):
            obj, _ = Fighter.objects.get_or_create(
                name=name,
                defaults={"sort_order": index},
            )
            fighters[name] = obj
        return fighters

    def _seed_matchups(self, fighters: dict[str, Fighter]) -> list[Matchup]:
        sorted_names = sorted(fighters.keys())
        matchups: list[Matchup] = []
        for index, (a_name, b_name) in enumerate(combinations(sorted_names, 2)):
            a = fighters[a_name]
            b = fighters[b_name]
            obj, _ = Matchup.objects.get_or_create(
                fighter_a=a,
                fighter_b=b,
                defaults={"sort_order": index},
            )
            matchups.append(obj)
        return matchups

    def _seed_fighter_tips(self, fighters: dict[str, Fighter]) -> None:
        sort_index = 0
        for name in sorted(fighters.keys()):
            fighter = fighters[name]
            for modifier in (5, -5):
                sign = "+" if modifier > 0 else "-"
                label = f"{fighter.name} {sign}{abs(modifier)}%"
                TipDefinition.objects.get_or_create(
                    label=label,
                    defaults={
                        "tip_type": TipDefinition.TipType.FIGHTER,
                        "fighter": fighter,
                        "matchup": None,
                        "target_fighter": fighter,
                        "modifier": modifier,
                        "sort_order": sort_index,
                    },
                )
                sort_index += 1

    def _seed_matchup_tips(self, matchups: list[Matchup]) -> None:
        sort_index = 0
        for matchup in matchups:
            for target in (matchup.fighter_a, matchup.fighter_b):
                other = (
                    matchup.fighter_b
                    if target == matchup.fighter_a
                    else matchup.fighter_a
                )
                label = f"{target.name} +10% vs {other.name}"
                TipDefinition.objects.get_or_create(
                    label=label,
                    defaults={
                        "tip_type": TipDefinition.TipType.MATCHUP,
                        "fighter": None,
                        "matchup": matchup,
                        "target_fighter": target,
                        "modifier": 10,
                        "sort_order": sort_index,
                    },
                )
                sort_index += 1
