"""django-allauth adapters.

The whole purpose of these adapters is one feature: every new user who shows
up via Discord/Google is created with ``is_active=False`` so they can't make
tips until the admin flips the flag in /admin/auth/user/. Until then, allauth
routes them to /accounts/inactive/ where they see a "pending approval" page.

Existing users (whose admin has already approved them) breeze through the
same OAuth flow with no friction on subsequent logins.

Notes on what we override and why:

* ``HotTipsAccountAdapter.is_open_for_signup``
    Disables the email/password signup form. The only path to an account is
    through a social provider. Admins can still create local users in
    /admin/auth/user/add/ (that bypasses the adapter).

* ``HotTipsSocialAccountAdapter.populate_user``
    Maps social profile fields onto ``User.first_name`` (used by our existing
    ``display_name`` helper) so the contributor's Discord/Google display name
    shows up in the UI without further wiring.

* ``HotTipsSocialAccountAdapter.save_user``
    Sets ``is_active=False`` on first signup so the user enters the "pending
    admin approval" bucket.
"""
from __future__ import annotations

from typing import Any

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest


class HotTipsAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        # No self-service local signups. Use a social provider or have the
        # admin create the account.
        return False


def _social_display_name(sociallogin: Any) -> str:
    """Pick the friendliest display name from a social account payload."""
    data = sociallogin.account.extra_data or {}
    # Discord: prefer global_name (the "display name" you see in chat), then
    # username. Discord doesn't expose "first_name" so we put the full
    # display name into first_name and our serializer surfaces that.
    for key in ("global_name", "given_name", "name", "username"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class HotTipsSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: Any,
        data: dict[str, Any],
    ):
        user = super().populate_user(request, sociallogin, data)
        # Backfill first_name from the social profile so display_name() picks
        # it up. Don't clobber a value the parent already set.
        if not (user.first_name or "").strip():
            user.first_name = _social_display_name(sociallogin)[:150]
        return user

    def save_user(self, request: HttpRequest, sociallogin: Any, form=None):
        user = super().save_user(request, sociallogin, form)
        # New social signups are inactive until an admin approves them.
        # Existing users (already approved or already inactive) are untouched
        # because allauth only calls save_user() on first-time signups.
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return user
