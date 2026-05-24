"""Root URL configuration.

Layout:
    /admin/               Django admin
    /api/                 DRF endpoints (arena/, auth/)
    /accounts/            django-allauth (login, logout, social OAuth, inactive,
                          password reset/change/set)
    /                     Catch-all serving the React app's index.html
"""
from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

# Visiting the SPA entry point sets/refreshes the CSRF cookie so React's first
# state fetch can include the X-CSRFToken header without an extra round-trip.
index_view = ensure_csrf_cookie(TemplateView.as_view(template_name="index.html"))

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("arena.urls")),
    # django-allauth provides: /accounts/login/, /accounts/logout/,
    # /accounts/inactive/, /accounts/<provider>/login/, /accounts/password/...
    path("accounts/", include("allauth.urls")),
    path("", index_view, name="index"),
]
