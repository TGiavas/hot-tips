"""Tests for the allauth adapters and the inactive-user gate.

The contract we're locking in here:

1. ``/accounts/signup/`` (the email/password signup URL) redirects to login,
   so there's no self-service local signup form. NB: the account adapter's
   ``is_open_for_signup`` *does* return True — allauth shares that flag with
   the social signup helper, so we have to block at the URL level instead.
2. ``HotTipsSocialAccountAdapter.save_user`` flips ``is_active`` to False on
   first-time social signups, regardless of what allauth's defaults would do.
3. Inactive users still can't toggle tips even with a valid session.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def _make_request(rf, method="post", path="/"):
    """Build a request with a real session attached.

    allauth's social ``save_user`` reaches into ``request.session`` to pull
    out the "verified email" stash, so a bare ``RequestFactory`` request
    blows up with ``AttributeError: 'WSGIRequest' object has no attribute
    'session'``. Attaching a SessionStore mimics what
    ``SessionMiddleware`` does in production.
    """
    request = getattr(rf, method)(path)
    request.session = SessionStore()
    return request


def test_email_signup_url_redirects_to_login(client):
    """The email/password signup form must be unreachable.

    We can't simply return False from the account adapter (that would also
    block Discord onboarding), so the URL is intercepted in hot_tips.urls
    and bounces both GET and POST back to the login page.
    """
    for response in (client.get("/accounts/signup/"), client.post("/accounts/signup/")):
        assert response.status_code in (301, 302)
        assert response["Location"].rstrip("/") == "/accounts/login"


def test_social_adapter_marks_new_users_inactive(rf):
    """A brand-new social signup ends up with ``is_active=False``."""
    from allauth.socialaccount.models import SocialAccount, SocialLogin
    from arena.adapters import HotTipsSocialAccountAdapter

    user_model = get_user_model()
    user = user_model(
        username="newcomer",
        email="newcomer@example.com",
        first_name="Newcomer",
    )
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(
            provider="discord",
            uid="discord-1234",
            extra_data={"global_name": "Newcomer"},
        ),
    )

    adapter = HotTipsSocialAccountAdapter()
    saved = adapter.save_user(_make_request(rf), sociallogin)

    assert saved.pk is not None
    assert saved.is_active is False, (
        "social signups must be inactive until an admin approves them"
    )


def test_social_adapter_populates_first_name_from_discord_global_name(rf):
    from allauth.socialaccount.models import SocialAccount, SocialLogin
    from arena.adapters import HotTipsSocialAccountAdapter

    user_model = get_user_model()
    user = user_model(username="auto", email="auto@example.com")
    sociallogin = SocialLogin(
        user=user,
        account=SocialAccount(
            provider="discord",
            uid="discord-9999",
            extra_data={"global_name": "Sir Galahad"},
        ),
    )

    adapter = HotTipsSocialAccountAdapter()
    populated = adapter.populate_user(_make_request(rf, "get"), sociallogin, {})
    assert populated.first_name == "Sir Galahad"


def test_deactivated_user_session_is_blocked(seeded, tips):
    """A user who gets deactivated mid-session can't keep toggling tips.

    Django's auth middleware loads the session user via
    ``ModelBackend.get_user``, which filters out users with ``is_active=False``
    and returns an ``AnonymousUser`` instead. So the very next request after
    the admin deactivates them is rejected without any explicit check in our
    code.
    """
    pwd = "secret-pw-123!xyz"
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="bob", password=pwd, first_name="Bob",
    )
    client = APIClient()
    assert client.login(username="bob", password=pwd)

    user.is_active = False
    user.save(update_fields=["is_active"])

    tip = next(iter(tips.values()))
    response = client.post(
        reverse("arena-toggle"),
        {"tip_id": tip.id},
        format="json",
    )
    assert response.status_code in (401, 403)


def test_inactive_user_cannot_login(seeded):
    """``client.login`` (ModelBackend) refuses inactive accounts upfront."""
    pwd = "secret-pw-123!xyz"
    user_model = get_user_model()
    user_model.objects.create_user(
        username="pending",
        password=pwd,
        first_name="Pending",
        is_active=False,
    )
    client = APIClient()
    assert client.login(username="pending", password=pwd) is False


@pytest.fixture
def rf():
    from django.test import RequestFactory

    return RequestFactory()
