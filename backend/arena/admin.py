"""Django admin registrations.

Static data (fighters, matchups, tip definitions) is fully editable. Daily
selections are editable for manual correction (per SPEC.md section 15).
The audit log is read-only.

User admin highlights pending OAuth signups: anyone who lands via Discord
starts with ``is_active=False`` (see ``arena.adapters``), so the list view
defaults to "Pending approval" so they're not buried under the noise of
already-approved members.
"""
from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import (
    DailyTipAuditLog,
    DailyTipSelection,
    Fighter,
    Matchup,
    SpreadsheetSyncConfig,
    TipDefinition,
)


@admin.register(Fighter)
class FighterAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("name",)
    ordering = ("sort_order", "name")


@admin.register(Matchup)
class MatchupAdmin(admin.ModelAdmin):
    list_display = ("__str__", "fighter_a", "fighter_b", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    autocomplete_fields = ("fighter_a", "fighter_b")
    list_filter = ("is_active",)
    search_fields = ("fighter_a__name", "fighter_b__name")


@admin.register(TipDefinition)
class TipDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "tip_type",
        "fighter",
        "matchup",
        "target_fighter",
        "modifier",
        "sort_order",
        "is_active",
    )
    list_filter = ("tip_type", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("label",)
    autocomplete_fields = ("fighter", "matchup", "target_fighter")


@admin.register(DailyTipSelection)
class DailyTipSelectionAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "tip",
        "submitted_by",
        "external_submitter_name",
        "updated_at",
    )
    list_filter = ("date",)
    search_fields = ("tip__label", "external_submitter_name")
    autocomplete_fields = ("tip",)
    raw_id_fields = ("submitted_by",)


@admin.register(DailyTipAuditLog)
class DailyTipAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "date",
        "tip",
        "action",
        "actor",
        "external_actor_name",
    )
    list_filter = ("action", "date")
    search_fields = (
        "tip__label",
        "actor__username",
        "external_actor_name",
    )
    readonly_fields = (
        "date",
        "tip",
        "action",
        "actor",
        "external_actor_name",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:  # type: ignore[override]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[override]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[override]
        return False


@admin.register(SpreadsheetSyncConfig)
class SpreadsheetSyncConfigAdmin(admin.ModelAdmin):
    """Singleton row: admin edits ``share_url`` / ``enabled``; the rest is
    read-only telemetry written by ``arena.sync``.
    """

    list_display = (
        "__str__",
        "enabled",
        "last_status",
        "last_run_at",
        "last_sheet_date",
        "last_added_count",
        "last_skipped_count",
    )
    readonly_fields = (
        "last_run_at",
        "last_status",
        "last_message",
        "last_sheet_date",
        "last_added_count",
        "last_skipped_count",
    )
    fieldsets = (
        (
            "Source",
            {
                "fields": ("share_url", "enabled"),
                "description": (
                    "Paste the OneDrive share URL for the community Hot "
                    "Tips spreadsheet. Anyone-with-the-link must have "
                    "view access. Toggle ``enabled`` off to pause both "
                    "the manual button and the periodic auto-sync."
                ),
            },
        ),
        (
            "Last run",
            {
                "fields": (
                    "last_run_at",
                    "last_status",
                    "last_sheet_date",
                    "last_added_count",
                    "last_skipped_count",
                    "last_message",
                ),
            },
        ),
    )

    def has_add_permission(self, request) -> bool:  # type: ignore[override]
        # Singleton: hide the "Add" button. The migration seeds pk=1 and
        # :meth:`SpreadsheetSyncConfig.save` clamps the pk on every save.
        return not SpreadsheetSyncConfig.objects.exists()

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[override]
        return False


# ---------------------------------------------------------------------------
# User admin: highlight pending OAuth signups + "Approve" action.
# Local user creation still works the standard way (admin sets a password).
# ---------------------------------------------------------------------------


User = get_user_model()
admin.site.unregister(User)


@admin.action(description="Approve selected users (set Active)")
def approve_users(modeladmin, request, queryset):
    updated = queryset.filter(is_active=False).update(is_active=True)
    if updated:
        modeladmin.message_user(
            request,
            f"Approved {updated} user{'s' if updated != 1 else ''}.",
            level=messages.SUCCESS,
        )
    skipped = queryset.count() - updated
    if skipped:
        modeladmin.message_user(
            request,
            f"Skipped {skipped} already-active user{'s' if skipped != 1 else ''}.",
            level=messages.INFO,
        )


class PendingApprovalListFilter(admin.SimpleListFilter):
    """Quick filter mirroring the most common admin task here."""

    title = "approval state"
    parameter_name = "approval"

    def lookups(self, request, model_admin):
        return (
            ("pending", "Pending approval"),
            ("approved", "Approved (active)"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        # NOTE: ``None`` (no query param) must filter the same way as
        # ``pending`` — otherwise the filter UI shows "Pending approval" as
        # selected on first page load while the queryset silently returns
        # *all* users, creating a misleading display state.
        value = self.value()
        if value in (None, "pending"):
            return queryset.filter(is_active=False)
        if value == "approved":
            return queryset.filter(is_active=True)
        return queryset

    def choices(self, changelist):
        # Default to "pending" when the page first loads so admins see the
        # signup queue immediately. Override the "All" link to clear it.
        yield {
            "selected": self.value() in (None, "pending"),
            "query_string": changelist.get_query_string(
                {self.parameter_name: "pending"}
            ),
            "display": "Pending approval",
        }
        for lookup, title in (("approved", "Approved (active)"), ("all", "All")):
            yield {
                "selected": self.value() == lookup,
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup}
                ),
                "display": title,
            }


@admin.register(User)
class HotTipsUserAdmin(UserAdmin):
    actions = [approve_users]
    list_display = (
        "username",
        "discord_display_name",
        "email",
        "social_providers",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = (PendingApprovalListFilter, "is_staff", "is_superuser")
    ordering = ("is_active", "-date_joined")

    @admin.display(description="Discord display name")
    def discord_display_name(self, obj) -> str:
        """Live display name pulled from the Discord SocialAccount.

        We prefer this over ``User.first_name`` because ``first_name`` is
        only a cache that gets populated on signup / refreshed on each
        social login (see ``arena.adapters.HotTipsSocialAccountAdapter``).
        Reading straight from ``extra_data`` shows the freshest value
        Discord returned, with sensible fallbacks if ``global_name`` is
        null.
        """
        for sa in obj.socialaccount_set.all():
            if sa.provider != "discord":
                continue
            data = sa.extra_data or {}
            return (
                data.get("global_name")
                or data.get("username")
                or obj.first_name
                or "—"
            )
        return obj.first_name or "—"

    @admin.display(description="Social")
    def social_providers(self, obj) -> str:
        providers = obj.socialaccount_set.values_list("provider", flat=True)
        return ", ".join(sorted(set(providers))) or "—"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related("socialaccount_set")
        )
