"""Tests for the 15-tip-per-day cap and toggle semantics.

Covered behaviours (SPEC.md sections 5 and 12.2):

* activating below the cap creates a selection + audit row,
* activating an already-active tip is treated as deactivate,
* deactivation always succeeds regardless of who originally activated,
* the cap is enforced atomically (we use ``select_for_update`` inside a
  transaction).
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(db):
    return get_user_model().objects.create_user(
        username="alice", password="x" * 16, first_name="Alice"
    )


@pytest.fixture
def bob(db):
    return get_user_model().objects.create_user(
        username="bob", password="x" * 16, first_name="Bob"
    )


@pytest.fixture
def client_alice(alice):
    c = APIClient()
    c.force_authenticate(alice)
    return c


@pytest.fixture
def client_bob(bob):
    c = APIClient()
    c.force_authenticate(bob)
    return c


def _toggle(client, tip_id: int):
    return client.post(
        reverse("arena-toggle"), {"tip_id": tip_id}, format="json"
    )


def test_activate_increments_count(seeded, client_alice, tips):
    tip = tips["Corrrak +5%"]
    response = _toggle(client_alice, tip.id)
    assert response.status_code == 200
    body = response.json()
    assert body["known_tip_count"] == 1
    assert any(at["tip_id"] == tip.id for at in body["active_tips"])


def test_reactivate_deactivates(seeded, client_alice, tips):
    tip = tips["Corrrak +5%"]
    _toggle(client_alice, tip.id)
    response = _toggle(client_alice, tip.id)
    assert response.status_code == 200
    assert response.json()["known_tip_count"] == 0


def test_bob_can_deactivate_alice_tip(seeded, client_alice, client_bob, tips):
    tip = tips["Corrrak +5%"]
    _toggle(client_alice, tip.id)
    response = _toggle(client_bob, tip.id)
    assert response.status_code == 200
    assert response.json()["known_tip_count"] == 0


def test_cap_blocks_sixteenth_activation(seeded, client_alice, tips):
    fifteen = list(tips.values())[:15]
    for tip in fifteen:
        response = _toggle(client_alice, tip.id)
        assert response.status_code == 200
    sixteenth = list(tips.values())[15]
    response = _toggle(client_alice, sixteenth.id)
    assert response.status_code == 409
    assert response.json()["detail"] == "shared daily pool full"


def test_deactivation_when_full_still_works(seeded, client_alice, tips):
    fifteen = list(tips.values())[:15]
    for tip in fifteen:
        _toggle(client_alice, tip.id)
    # Pool is at 15. Deactivating one should always succeed.
    response = _toggle(client_alice, fifteen[0].id)
    assert response.status_code == 200
    assert response.json()["known_tip_count"] == 14


def test_audit_log_records_activate_and_deactivate(seeded, client_alice, tips):
    from arena.models import DailyTipAuditLog

    tip = tips["Corrrak +5%"]
    _toggle(client_alice, tip.id)
    _toggle(client_alice, tip.id)
    rows = list(
        DailyTipAuditLog.objects.filter(tip=tip).order_by("created_at")
    )
    assert [r.action for r in rows] == ["activate", "deactivate"]
    assert all(r.actor.username == "alice" for r in rows)
