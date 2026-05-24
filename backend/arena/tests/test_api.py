"""DRF API smoke tests.

These cover:

* unauthenticated requests return 401,
* ``GET /api/arena/state/`` returns the expected top-level keys,
* ``POST /api/arena/tips/toggle/`` validates the payload,
* ``GET /api/auth/whoami/`` reflects auth state.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    user = get_user_model().objects.create_user(
        username="alice", password="x" * 16, first_name="Alice"
    )
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_state_allows_anonymous(seeded):
    """Anonymous viewers can read the arena state (read-only mode)."""
    response = APIClient().get(reverse("arena-state"))
    assert response.status_code == 200
    body = response.json()
    assert body["known_tip_count"] == 0
    assert len(body["fighters"]) == 7


def test_toggle_requires_auth(seeded, tips):
    tip = next(iter(tips.values()))
    response = APIClient().post(
        reverse("arena-toggle"), {"tip_id": tip.id}, format="json"
    )
    assert response.status_code in (401, 403)


def test_state_shape(seeded, auth_client):
    response = auth_client.get(reverse("arena-state"))
    assert response.status_code == 200
    body = response.json()
    for key in (
        "game_day",
        "known_tip_count",
        "max_tips",
        "fighters",
        "matchups",
        "fighter_tips",
        "matchup_tips",
        "active_tips",
        "match_results",
    ):
        assert key in body, f"missing key {key!r}"
    assert body["max_tips"] == 15
    assert body["known_tip_count"] == 0
    assert len(body["fighters"]) == 7
    assert len(body["matchups"]) == 21
    assert len(body["fighter_tips"]) == 14
    assert len(body["matchup_tips"]) == 42
    # All 21 matchups start at 50/50.
    assert all(r["fighter_a_percent"] == 50 for r in body["match_results"])


def test_toggle_invalid_payload(seeded, auth_client):
    response = auth_client.post(
        reverse("arena-toggle"), {"tip_id": "not-an-int"}, format="json"
    )
    assert response.status_code == 400


def test_toggle_unknown_tip(seeded, auth_client):
    response = auth_client.post(
        reverse("arena-toggle"), {"tip_id": 999_999}, format="json"
    )
    assert response.status_code == 404


def test_whoami_unauthenticated_returns_401():
    response = APIClient().get(reverse("auth-whoami"))
    assert response.status_code == 401


def test_whoami_returns_display_name(auth_client):
    response = auth_client.get(reverse("auth-whoami"))
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"


def test_csrf_endpoint_sets_cookie():
    client = APIClient()
    response = client.get(reverse("auth-csrf"))
    assert response.status_code == 200
    assert "csrftoken" in response.cookies
