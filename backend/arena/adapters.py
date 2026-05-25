"""django-allauth adapters.

The whole purpose of these adapters is one feature: every new user who shows
up via Discord is created with ``is_active=False`` so they can't make tips
until the admin flips the flag in /admin/auth/user/. Until then, allauth
routes them to /accounts/inactive/ where they see a "pending approval" page.

Existing users (whose admin has already approved them) breeze through the
same OAuth flow with no friction on subsequent logins.

Notes on what we override and why:

* ``HotTipsAccountAdapter.is_open_for_signup``
    Returns True. NOTE: this gate is checked by allauth even on the social
    signup path (``socialaccount.helpers._process_signup``), so returning
    False breaks Discord onboarding. We instead block the email/password
    signup *URL* (``/accounts/signup/``) in ``hot_tips.urls`` so the form is
    never reachable.

* ``HotTipsSocialAccountAdapter.populate_user``
    Maps social profile fields onto ``User.first_name`` (used by our existing
    ``display_name`` helper) so the contributor's Discord display name shows
    up in the UI without further wiring. Runs once on first signup.

* ``HotTipsSocialAccountAdapter.pre_social_login``
    Runs on *every* social login (including returning users). Keeps
    ``User.first_name`` in sync with the freshest Discord ``global_name`` so
    when a user changes their display name on Discord, the UI picks it up
    the next time they sign in — no admin intervention needed.

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
        # Must return True: allauth's social-signup helper consults this same
        # flag and blocks Discord onboarding when it's False. The email/
        # password signup *URL* is disabled at the urlconf level instead (see
        # hot_tips.urls), so there's no actual self-service local signup
        # path even though this returns True.
        return True


def _social_display_name(sociallogin: Any) -> str:
    """Pick the friendliest display name from a social account payload.

    For Discord this prefers ``global_name`` (the user's changeable display
    name) and falls back to ``username`` (the unique handle).
    """
    data = sociallogin.account.extra_data or {}
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
        # it up. Force-set even if allauth already populated something — for
        # Discord allauth uses the first whitespace-separated chunk of
        # global_name, but for display we'd rather keep the full thing.
        display = _social_display_name(sociallogin)[:150]
        if display:
            user.first_name = display
        return user

    def pre_social_login(self, request: HttpRequest, sociallogin: Any) -> None:
        """Sync the cached display name with the freshest Discord value.

        Fires on every social login (new and returning users). For new
        users ``sociallogin.user.pk`` is None and we no-op; ``populate_user``
        will set things up at signup time. For returning users we refresh
        ``first_name`` so a Discord display-name change shows up in the UI
        on their next sign-in.
        """
        super().pre_social_login(request, sociallogin)
        user = sociallogin.user
        if not user.pk:
            return
        display = _social_display_name(sociallogin)[:150]
        if display and user.first_name != display:
            user.first_name = display
            user.save(update_fields=["first_name"])

    def save_user(self, request: HttpRequest, sociallogin: Any, form=None):
        user = super().save_user(request, sociallogin, form)
        # New social signups are inactive until an admin approves them.
        # Existing users (already approved or already inactive) are untouched
        # because allauth only calls save_user() on first-time signups.
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return user
