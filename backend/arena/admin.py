"""Django admin registrations.

Static data (fighters, matchups, tip definitions) is fully editable. Daily
selections are editable for manual correction (per SPEC.md section 15).
The audit log is read-only.

User admin highlights pending OAuth signups: anyone who lands via Discord or
Google starts with ``is_active=False`` (see ``arena.adapters``), so the list
view defaults to "Pending approval" so they're not buried under the noise of
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
    list_display = ("date", "tip", "submitted_by", "updated_at")
    list_filter = ("date",)
    search_fields = ("tip__label",)
    autocomplete_fields = ("tip",)
    raw_id_fields = ("submitted_by",)


@admin.register(DailyTipAuditLog)
class DailyTipAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "date", "tip", "action", "actor")
    list_filter = ("action", "date")
    search_fields = ("tip__label", "actor__username")
    readonly_fields = (
        "date",
        "tip",
        "action",
        "actor",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:  # type: ignore[override]
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # type: ignore[override]
        return False

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
        value = self.value()
        if value == "pending":
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
        "first_name",
        "email",
        "social_providers",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = (PendingApprovalListFilter, "is_staff", "is_superuser")
    ordering = ("is_active", "-date_joined")

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
