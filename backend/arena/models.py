"""Database models for the Arena Hot Tips tool.

See SPEC.md sections 2, 3, 5, and 11 for the conceptual model. The five tables
defined here are:

    Fighter            - an arena participant
    Matchup            - a fixed pair of distinct fighters (canonicalised so
                         "A vs B" and "B vs A" collapse to one row)
    TipDefinition      - a fixed modifier the user can toggle; either
                         fighter-wide (+/- 5%) or matchup-specific (+10%)
    DailyTipSelection  - one row per active tip in the shared daily pool
    DailyTipAuditLog   - immutable history of activate/deactivate events
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# Allowed modifier values per SPEC.md sections 3 and 14.
FIGHTER_TIP_MODIFIERS = {-5, 5}
MATCHUP_TIP_MODIFIER = 10
DAILY_TIP_CAP = 15


class Fighter(models.Model):
    name = models.CharField(max_length=100, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Matchup(models.Model):
    """A fixed pair of distinct fighters. Canonical ordering is enforced at the
    application level (see :func:`Matchup.clean`) and at the database level via
    the unique constraint on ``(fighter_a, fighter_b)``: we always store the
    pair with ``fighter_a`` having the lexicographically smaller name."""

    fighter_a = models.ForeignKey(
        Fighter, on_delete=models.PROTECT, related_name="matchups_as_a"
    )
    fighter_b = models.ForeignKey(
        Fighter, on_delete=models.PROTECT, related_name="matchups_as_b"
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "fighter_a__name", "fighter_b__name"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(fighter_a=models.F("fighter_b")),
                name="matchup_fighters_must_differ",
            ),
            models.UniqueConstraint(
                fields=["fighter_a", "fighter_b"],
                name="unique_ordered_matchup",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.fighter_a} vs {self.fighter_b}"

    def clean(self) -> None:
        if (
            self.fighter_a_id
            and self.fighter_b_id
            and self.fighter_a_id == self.fighter_b_id
        ):
            raise ValidationError("Matchup fighters must differ.")


class TipDefinition(models.Model):
    """A static modifier the user can toggle.

    Two flavours:

    * Fighter-wide: ``tip_type == FIGHTER`` -> ``fighter`` set, ``matchup``
      null, ``target_fighter`` equals ``fighter``, ``modifier in {-5, +5}``.
    * Matchup-specific: ``tip_type == MATCHUP`` -> ``matchup`` set, ``fighter``
      null, ``target_fighter`` is one of the matchup's two fighters,
      ``modifier == +10``.
    """

    class TipType(models.TextChoices):
        FIGHTER = "fighter", "Fighter"
        MATCHUP = "matchup", "Matchup"

    label = models.CharField(max_length=200, unique=True)
    tip_type = models.CharField(max_length=20, choices=TipType.choices)

    fighter = models.ForeignKey(
        Fighter,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fighter_tip_definitions",
    )
    matchup = models.ForeignKey(
        Matchup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tip_definitions",
    )
    target_fighter = models.ForeignKey(
        Fighter,
        on_delete=models.PROTECT,
        related_name="targeted_tip_definitions",
    )

    modifier = models.SmallIntegerField()
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["tip_type", "sort_order", "label"]

    def __str__(self) -> str:
        return self.label

    def clean(self) -> None:
        if self.tip_type == self.TipType.FIGHTER:
            if self.fighter_id is None:
                raise ValidationError(
                    {"fighter": "Fighter tip must reference a fighter."}
                )
            if self.matchup_id is not None:
                raise ValidationError(
                    {"matchup": "Fighter tip must not reference a matchup."}
                )
            if self.target_fighter_id != self.fighter_id:
                raise ValidationError(
                    {"target_fighter": "Fighter tip target must equal its fighter."}
                )
            if self.modifier not in FIGHTER_TIP_MODIFIERS:
                raise ValidationError(
                    {"modifier": "Fighter tip modifier must be +5 or -5."}
                )
        elif self.tip_type == self.TipType.MATCHUP:
            if self.matchup_id is None:
                raise ValidationError(
                    {"matchup": "Matchup tip must reference a matchup."}
                )
            if self.fighter_id is not None:
                raise ValidationError(
                    {"fighter": "Matchup tip must not reference a fighter directly."}
                )
            matchup = self.matchup
            if self.target_fighter_id not in (
                matchup.fighter_a_id,
                matchup.fighter_b_id,
            ):
                raise ValidationError(
                    {
                        "target_fighter": "Matchup tip target must be one of the "
                        "matchup's fighters."
                    }
                )
            if self.modifier != MATCHUP_TIP_MODIFIER:
                raise ValidationError(
                    {"modifier": "Matchup tip modifier must be +10."}
                )
        else:
            raise ValidationError({"tip_type": "Unknown tip type."})


class DailyTipSelection(models.Model):
    """The current set of active tips in the shared daily pool.

    A row exists if and only if the tip is currently active for the given game
    day. Deactivation deletes the row; re-activation creates a new row whose
    ``submitted_by`` records the most recent activator (matching the spec's
    "submitted/last activated" semantics).
    """

    date = models.DateField()
    tip = models.ForeignKey(TipDefinition, on_delete=models.PROTECT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="submitted_daily_tips",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["date", "tip"],
                name="unique_shared_date_tip_selection",
            ),
        ]
        ordering = ["date", "tip__sort_order", "tip__label"]

    def __str__(self) -> str:
        return f"{self.date} :: {self.tip} by {self.submitted_by}"


class DailyTipAuditLog(models.Model):
    """Immutable history of every activate/deactivate event."""

    class Action(models.TextChoices):
        ACTIVATE = "activate", "Activate"
        DEACTIVATE = "deactivate", "Deactivate"

    date = models.DateField()
    tip = models.ForeignKey(TipDefinition, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.tip} by {self.actor}"
