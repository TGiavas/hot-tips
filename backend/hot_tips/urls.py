"""Root URL configuration.

Layout:
    /admin/               Django admin
    /api/                 DRF endpoints (arena/, auth/)
    /accounts/            django-allauth (login, logout, social OAuth, inactive,
                          password reset/change/set)
    /                     Catch-all serving the React app's index.html

The /accounts/signup/ URL is intentionally intercepted *before* allauth's
include so the email/password signup form is unreachable. Our adapter has to
return ``is_open_for_signup=True`` (allauth checks the same flag for social
signups), so the URL-level block is what actually keeps random people from
self-registering.
"""
from __future__ import annotations

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

# Visiting the SPA entry point sets/refreshes the CSRF cookie so React's first
# state fetch can include the X-CSRFToken header without an extra round-trip.
index_view = ensure_csrf_cookie(TemplateView.as_view(template_name="index.html"))


def signup_disabled(request):
    """Bounce email/password signup requests back to the login page.

    The login page only exposes Discord OAuth; there is no public form for
    self-service local accounts. Handles both GET and POST so a programmatic
    POST can't sneak past this either.
    """
    return redirect("/accounts/login/")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("arena.urls")),
    # Must come *before* allauth.urls so it shadows allauth's SignupView.
    path("accounts/signup/", signup_disabled, name="account_signup"),
    # django-allauth provides: /accounts/login/, /accounts/logout/,
    # /accounts/inactive/, /accounts/<provider>/login/, /accounts/password/...
    path("accounts/", include("allauth.urls")),
    path("", index_view, name="index"),
]
