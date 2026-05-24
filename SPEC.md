# Arena Hot Tips Tool — Implementation Spec

## 1. Goal

Build a simple desktop web tool for a game’s arena matches.

Anyone can view the page (read-only). Authenticated users contribute one or more fixed Hot Tips to a shared daily tip pool. The app calculates win percentages for each fixed matchup based on the combined tips submitted by all authenticated users for that game day.

The game day resets at **12:00 AM EDT**. All date logic should use the game day, not the user’s local timezone.

The core UX is:

* users toggle the fixed tips they know for today
* all users contribute to one shared daily tip set
* each user may submit only one tip or several tips
* the shared daily pool is capped at 15 total tips
* see calculated matchup win percentages immediately
* every tip change is logged with the acting user

This is a small trusted-user tool, not a public app.

---

## 2. Key Concepts

### Fighter

A fighter is an arena participant.

Fighter names are fixed for v0.1.

### Matchup

A matchup is a fixed pair of fighters.

There are 21 possible matchups (all pairs of the 7 fighters).

`A vs B` and `B vs A` are the same logical matchup.

Each matchup starts at:

* Fighter A: 50%
* Fighter B: 50%

### Hot Tip

A Hot Tip is a fixed possible modifier.

Tips are not free text. Users select from fixed possible tips.

There are two categories:

1. Fighter-wide tips
2. Matchup-specific tips

NPCs are irrelevant and should not appear in the UI or data model.

---

## 3. Tip Types

### 3.1 Fighter-wide tip

Applies to all matches involving one fighter.

Possible effects:

* `+5%` for a fighter in all their matches
* `-5%` for a fighter in all their matches

Example:

```text
Akrul +5%
```

For every matchup containing Akrul:

```text
Akrul chance += 5
Opponent chance -= 5
```

Negative example:

```text
Akrul -5%
```

For every matchup containing Akrul:

```text
Akrul chance -= 5
Opponent chance += 5
```

### 3.2 Matchup-specific tip

Applies only to one specific matchup.

Possible effect:

* `+10%` for one fighter in that specific matchup

Example:

```text
Akrul +10% vs Bremnor
```

For only that matchup:

```text
Akrul chance += 10
Bremnor chance -= 10
```

---

## 4. Conflicts

Conflicting tips are allowed.

Examples:

```text
Akrul +5%
Akrul -5%
```

or:

```text
Akrul +10% vs Bremnor
Bremnor +10% vs Akrul
```

The app should not block these.

The calculation simply adds all modifiers together.

Conflict detection is optional for v0.1. Correct calculation is required.

---

## 5. Daily Shared Tip Rule

The game has 15 total Hot Tips per game day across all users.

Each individual user may know only a few tips, possibly even just one.

Rules:

* tips are submitted by users
* the displayed daily tip pool is shared across all users
* any authenticated user can activate or deactivate any tip
* the total shared active tips must not exceed 15
* the app must not require a single user to enter all 15 tips
* active tips should show who submitted or last activated them
* every activation/deactivation must be audit-logged

UI behavior:

* show shared counter: `Known tips today: X / 15`
* allow any authenticated user to activate/deactivate any tip
* if the shared pool already has 15 tips, prevent adding more new tips
* active tips submitted by another user are still editable/removable
* updating is immediate; no separate final save action is required

Default decision:

```text
Each button press updates the shared daily tip pool and writes an audit log entry.
```

---

## 6. Authentication

Use Django built-in authentication.

Requirements:

* anyone (including anonymous visitors) can view the arena state
* only authenticated users can activate/deactivate tips
* public registration is disabled
* users are created manually by an admin (via the "send password-set link" admin action)
* Django admin is used for managing fighters, matchups, and fixed tip definitions

For v0.1:

* all authenticated users may contribute, add, or remove shared daily tips
* admin users manage static data

Optional later:

* add permissions such as `can_submit_arena_tips`
* add token/API-key access for external scripts

---

## 7. Main UI

Desktop only.

No mobile optimization required for v0.1.

Single main page:

```text
┌─────────────────────────────────────────────────────────────┐
│ Game day: 2026-05-24   Known tips: 12 / 15   Reset: 12 AM EDT│
└─────────────────────────────────────────────────────────────┘

┌───────────────────────────────┬─────────────────────────────┐
│ Tip Selection                 │ Match Results               │
│                               │                             │
│ [Fighter Tips] [Matchup Tips] │ Fighter A | A % | Fighter B │
│                               │ Akrul     | 65 | Bremnor   │
│ grid of toggles               │ Dorga     | 50 | Setti     │
└───────────────────────────────┴─────────────────────────────┘
```

Header contains:

* current game day
* shared known tip count
* reset reference: 12:00 AM America/New_York (DST-aware)

Date behavior:

* only today is editable; there is no date picker in v0.1
* backend calculates the current game day in `America/New_York`
* do not trust the browser timezone for game-day calculation

---

## 8. Tip Selection UI

Use tabs:

```text
[Fighter Tips] [Matchup Tips]
```

### 8.1 Fighter Tips tab

Grid/table layout:

```text
Fighter      Positive                    Negative
Akrul        [ +5% ]                     [ -5% ]
Bremnor      [ +5% submitted by Maria ]  [ -5% ]
Dorga        [ +5% ]                     [ -5% submitted by Nick ]
Setti        [ +5% ]                     [ -5% ]
```

Each button is a toggle.

States:

* inactive: neutral/outline
* active: highlighted/filled and removable by any authenticated user
* disabled: inactive button disabled when the shared pool already has 15 tips

Active tips should display submitter information:

```text
+5% submitted by Themis
```

or shorter:

```text
+5% · Themis
```

### 8.2 Matchup Tips tab

Grid/table layout:

```text
Matchup             Fighter A Tip             Fighter B Tip
Akrul vs Bremnor    [ Akrul +10% · Themis ]   [ Bremnor +10% ]
Dorga vs Setti      [ Dorga +10% ]            [ Setti +10% · Maria ]
Korr vs Mela        [ Korr +10% ]             [ Mela +10% ]
```

A matchup may have both sides active if conflicting tips exist.

Do not enforce mutual exclusion.

Shared-edit behavior:

* if a tip is inactive, clicking it activates it and records the current user as submitter/last activator
* if a tip is active, clicking it removes it regardless of who submitted it
* the same tip definition can only appear once in the shared daily pool
* the frontend should show who submitted/last activated each active tip

---

## 9. Match Results UI

The match table should be minimal.

Columns:

```text
Fighter A | A % | Fighter B | B %
```

Example:

```text
Fighter A   A %   Fighter B   B %
Akrul       65    Bremnor     35
Dorga       50    Setti       50
Korr        45    Mela        55
```

Rules:

* no extra columns in the main table
* no raw modifier columns
* no tip-count columns
* no status columns

The main table is for quick scanning only.

Optional later:

* click a row to show applied tips in a side panel or expandable detail area

For v0.1, row details are optional.

---

## 10. Calculation Rules

Each matchup starts at 50/50.

For every active shared tip submitted by any user:

* if the tip applies to Fighter A, add modifier to Fighter A
* if the tip applies to Fighter B, add modifier to Fighter B
* because the two fighters’ odds must sum to 100, applying `+X` to one side subtracts `X` from the other side

Recommended implementation:

```python
fighter_a_percent = 50

for tip in active_tips:
    if tip applies to this matchup:
        if tip.target_fighter == matchup.fighter_a:
            fighter_a_percent += tip.modifier
        elif tip.target_fighter == matchup.fighter_b:
            fighter_a_percent -= tip.modifier

fighter_a_percent = clamp(fighter_a_percent, 0, 100)
fighter_b_percent = 100 - fighter_a_percent
```

Important:

* `modifier` can be `-5`, `+5`, or `+10`
* fighter-wide negative tips can be represented as `modifier = -5`
* matchup tips should usually be `modifier = +10`

Example:

```text
Akrul vs Bremnor
Active tips:
- Akrul +5%
- Bremnor -5%
- Akrul +10% vs Bremnor

Akrul = 50 + 5 + 5 + 10 = 70
Bremnor = 30
```

---

## 11. Data Model

Suggested Django models.

### 11.1 Fighter

```python
class Fighter(models.Model):
    name = models.CharField(max_length=100, unique=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name
```

### 11.2 Matchup

```python
class Matchup(models.Model):
    fighter_a = models.ForeignKey(
        Fighter,
        on_delete=models.PROTECT,
        related_name="matchups_as_a",
    )
    fighter_b = models.ForeignKey(
        Fighter,
        on_delete=models.PROTECT,
        related_name="matchups_as_b",
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "fighter_a__name", "fighter_b__name"]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(fighter_a=models.F("fighter_b")),
                name="matchup_fighters_must_differ",
            ),
            models.UniqueConstraint(
                fields=["fighter_a", "fighter_b"],
                name="unique_ordered_matchup",
            ),
        ]

    def __str__(self):
        return f"{self.fighter_a} vs {self.fighter_b}"
```

Because `A vs B` and `B vs A` are the same logical matchup, enforce canonical ordering when creating matchups or during seed import.

### 11.3 TipDefinition

```python
class TipDefinition(models.Model):
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

    def __str__(self):
        return self.label
```

Validation rules:

* fighter tip must have `fighter` set and `matchup` null
* matchup tip must have `matchup` set
* target fighter must match the fighter/matchup
* fighter-wide modifier allowed values: `-5`, `5`
* matchup-specific modifier allowed value: `10`

### 11.4 DailyTipSelection

Stores the current active shared tips for a game day.

```python
class DailyTipSelection(models.Model):
    date = models.DateField()
    tip = models.ForeignKey(TipDefinition, on_delete=models.PROTECT)

    # User who most recently activated/submitted this tip for this game day.
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
            )
        ]
```

Validation:

* a game day should not have more than 15 active selected tips total
* the same tip can only be submitted once per game day
* any authenticated user can remove any active tip

### 11.5 DailyTipAuditLog

Stores every change to the shared daily tip pool.

```python
class DailyTipAuditLog(models.Model):
    class Action(models.TextChoices):
        ACTIVATE = "activate", "Activate"
        DEACTIVATE = "deactivate", "Deactivate"

    date = models.DateField()
    tip = models.ForeignKey(TipDefinition, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
```

Use this for accountability and debugging.

No separate daily save model is required for v0.1. The shared daily state is the set of `DailyTipSelection` rows for that game day.

---

## 12. Backend API

Use Django REST Framework.

### 12.1 Get arena state

```text
GET /api/arena/state/
```

Always returns state for the current game day (computed server-side in `America/New_York`). No `date` query parameter in v0.1.

Returns:

* current game day
* fighters
* matchups
* tip definitions grouped by tab
* shared active selected tips for the selected game day
* submitter display name for each active tip
* calculated match results
* known tip count

Example response shape:

```json
{
  "game_day": "2026-05-24",
  "known_tip_count": 12,
  "max_tips": 15,
  "fighter_tips": [],
  "matchup_tips": [],
  "active_tips": [
    {
      "tip_id": 123,
      "submitted_by": {
        "id": 5,
        "display_name": "Themis"
      }
    }
  ],
  "match_results": [
    {
      "matchup_id": 1,
      "fighter_a": "Akrul",
      "fighter_a_percent": 65,
      "fighter_b": "Bremnor",
      "fighter_b_percent": 35
    }
  ]
}
```

### 12.2 Toggle tip

```text
POST /api/arena/tips/toggle/
```

Payload:

```json
{
  "tip_id": 123
}
```

The server uses the current game day automatically.

Behavior:

* if tip is inactive for that game day, activate it for the current user unless the shared pool is already at 15
* if tip is active, deactivate it regardless of who submitted it
* write a `DailyTipAuditLog` row for every activation/deactivation
* return the full updated arena state, or at minimum updated active tips + calculated results + known tip count

No separate save/reset endpoints are required for v0.1.

Optional later:

* audit log endpoint
* clear-my-tips-for-today endpoint
* API token endpoint for external clients

---

## 13. Frontend Technology

Use:

```text
React + Django REST API
```

Recommended frontend:

```text
React + Vite + TypeScript
```

Recommended backend:

```text
Django + Django REST Framework
```

Reasoning:

* the project needs a proper API anyway
* the toggle grid is naturally state-driven
* the frontend can update after API responses
* external clients/scripts can reuse the same API later

Authentication options:

For browser app:

```text
Django session auth + CSRF
```

For external scripts later:

```text
Token auth or API keys
```

Default v0.1 decision:

```text
React frontend talks to Django REST API using session authentication.
```

---

## 14. Validation Rules

Required:

* anonymous users may read the arena state; mutating endpoints require authentication
* selected tip must exist and be active
* selected game day must be valid
* shared daily pool cannot exceed 15 tips for a game day
* any authenticated user can remove any active shared tip
* every activation/deactivation must create an audit log entry
* tip definitions cannot be invalid in admin

Admin validation:

* fighter-wide tip target must equal its fighter
* matchup-specific tip target must be one of the matchup fighters
* fighter-wide tip modifier must be `+5` or `-5`
* matchup-specific tip modifier must be `+10`

---

## 15. Admin Usage

Use Django admin for static data.

Admin manages:

* fighters
* matchups
* tip definitions
* users
* daily tip selections if manual correction is needed
* audit logs as read-only records

No custom admin UI needed for v0.1.

---

## 16. Permissions

v0.1:

* anyone can view the arena state (no login required)
* authenticated users can add/remove shared daily tips
* staff/admin users can edit static data in Django admin

Optional later:

* only users in a specific group can access the arena tool
* add permission: `arena.use_tool`

---

## 17. Styling Guidance

Keep the UI dense and boring.

Main principles:

* desktop-first
* minimal columns
* no card-heavy UI
* active toggles should be visually obvious
* disabled toggles should be visually obvious
* main match table should stay clean
* submitter names should be visible but not visually dominant

Suggested layout:

```text
Top header
Two-column workspace
Left: fixed tip toggle grid
Right: minimal result table
```

Suggested table columns:

Match Results:

```text
Fighter A | A % | Fighter B | B %
```

Fighter Tips:

```text
Fighter | +5% | -5%
```

Matchup Tips:

```text
Matchup | Fighter A +10% | Fighter B +10%
```

---

## 18. Example Calculation Dataset

Example active tips:

```text
Akrul +5% submitted by Themis
Bremnor -5% submitted by Maria
Akrul +10% vs Bremnor submitted by Nick
Dorga +5% submitted by Themis
Setti +5% submitted by Alex
```

For `Akrul vs Bremnor`:

```text
Start: Akrul 50 / Bremnor 50
Akrul +5 => Akrul 55 / Bremnor 45
Bremnor -5 => Akrul 60 / Bremnor 40
Akrul +10 vs Bremnor => Akrul 70 / Bremnor 30
Final: Akrul 70 / Bremnor 30
```

For `Dorga vs Setti`:

```text
Start: Dorga 50 / Setti 50
Dorga +5 => Dorga 55 / Setti 45
Setti +5 => Dorga 50 / Setti 50
Final: Dorga 50 / Setti 50
```

---

## 19. v0.1 Scope

Include:

* login/logout
* React main arena page
* current game day shown in header (no date picker)
* fighter tip grid
* matchup tip grid
* shared known-tip counter
* max 15 shared active tips per game day
* submitted-by display for active tips
* audit logging for every change
* calculated matchup results table
* Django REST API
* Django admin for data setup
* polling refresh every 10s for multi-user updates
* admin "send password-set link" flow for onboarding new users

Exclude:

* mobile optimization
* public registration
* payment
* complex analytics
* historical charts
* real-time collaboration
* NPC-specific input
* custom role system unless needed later

---

## 20. Resolved Decisions

```text
Tips are submitted by users but combined into one shared daily tip set.
NPCs are irrelevant and should not appear in the UI or data model.
Each user can submit from 1 to 15 tips; the total shared game-day pool is capped at 15.
Any authenticated user can remove any active shared tip.
Every change must be audit-logged with the acting user.
The frontend should show who submitted/last activated each active tip.
The game day resets at midnight America/New_York (DST-aware).
Matchups and fighter names are fixed.
No history page is needed for v0.1.
A vs B and B vs A are the same logical matchup.
Use React + Django REST API.
Only today is editable; no date picker in v0.1.
Multi-user sync via polling every 10s when the tab is visible.
There are 21 matchups (all pairs of the 7 fighters: Corrrak, Dura, Gloz, Leo, Otis, Ushug, Viz).
Users are onboarded by admin via a "send password-set link" action (no public signup, no email infra).
Production runs as a single Docker image (Django + gunicorn + whitenoise serving the built React bundle) targeting Fly.io with a persistent volume for SQLite.
```

---

## 21. Suggested First Implementation Steps

1. Create Django project and app.
2. Add Django REST Framework.
3. Add models: `Fighter`, `Matchup`, `TipDefinition`, `DailyTipSelection`, `DailyTipAuditLog`.
4. Register models in Django admin.
5. Seed fighters, 22 matchups, and fixed tip definitions.
6. Implement game-day calculation based on 12:00 AM EDT.
7. Implement matchup probability calculation service.
8. Add API endpoint for arena state.
9. Add API endpoint for tip toggling with audit logging.
10. Create React + Vite + TypeScript frontend.
11. Build two-column desktop layout: tip grid left, match results right.
12. Add validation around the shared 15-tip game-day cap.
13. Deploy after local testing.
