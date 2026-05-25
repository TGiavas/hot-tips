"""Django settings for the Arena Hot Tips project.

Environment variables (all optional in dev):
    DJANGO_DEBUG           "true"/"false" (default "true")
    DJANGO_SECRET_KEY      required when DEBUG=false
    DJANGO_ALLOWED_HOSTS   comma-separated, e.g. "hot-tips.example.com"
    DJANGO_CSRF_TRUSTED    comma-separated full origins, e.g. "https://hot-tips.example.com"
    DJANGO_DB_PATH         absolute path to SQLite file (default: backend/db.sqlite3)
    DISCORD_CLIENT_ID      OAuth2 Client ID from https://discord.com/developers
    DISCORD_CLIENT_SECRET  OAuth2 Client Secret from same page

Auth model:
    * Anyone can read the arena state (anonymous GET allowed).
    * To make a tip, you need an *active* account.
    * New users sign up via Discord OAuth (django-allauth).
    * Every social signup creates a user with ``is_active=False`` and lands
      on /accounts/inactive/ until an admin flips ``is_active`` in
      /admin/auth/user/.
    * Admins can still log into /admin/ with a username/password the normal
      way (createsuperuser etc.).
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-insecure-change-me-please" if DEBUG else "",
)
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false."
    )

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS",
        "*" if DEBUG else "",
    ).split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED", "").split(",")
    if o.strip()
]
# In dev, the React app is served by Vite at :5173 and proxies /accounts,
# /admin, /api to Django at :8000. The browser's Origin header on form
# submissions is therefore http://localhost:5173, which Django's CSRF
# middleware rejects unless it's explicitly trusted.
if DEBUG:
    for dev_origin in (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ):
        if dev_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(dev_origin)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # django-allauth requirements:
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.discord",
    "rest_framework",
    "arena",
]

# allauth uses django.contrib.sites for SocialApp scoping. Single-site app.
SITE_ID = 1

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves the built React bundle + Django static assets in production.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth must come after AuthenticationMiddleware.
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "hot_tips.urls"

# The built React bundle (when present) is mounted as a template dir so that
# `index.html` can be rendered as a Django template at the catch-all route.
# We prepend it so the production index wins over the dev fallback template.
FRONTEND_DIST = BASE_DIR / "frontend_dist"
TEMPLATE_DIRS: list = []
if FRONTEND_DIST.exists():
    TEMPLATE_DIRS.append(FRONTEND_DIST)
TEMPLATE_DIRS.append(BASE_DIR / "templates")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": TEMPLATE_DIRS,
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "hot_tips.wsgi.application"
ASGI_APPLICATION = "hot_tips.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get(
            "DJANGO_DB_PATH", str(BASE_DIR / "db.sqlite3")
        ),
        "OPTIONS": {
            "timeout": 20,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"

# Game-day logic uses America/New_York explicitly in services.current_game_day().
# Internally Django stores timestamps in UTC.
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [FRONTEND_DIST] if FRONTEND_DIST.exists() else []
# Plain compression — no hashing/manifest. Vite already content-hashes asset
# filenames, so the references inside index.html stay valid.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth & session ---
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
# Both the Header "Log out" button and the "Return to Hot Tips" button on
# /accounts/inactive/ point at /accounts/logout/. Sending users to the arena
# afterwards (rather than back to the login form) feels right in both cases —
# logged-out viewers can still see the read-only state.
LOGOUT_REDIRECT_URL = "/"

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# In prod with HTTPS we want secure cookies; toggled by env.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# Whitenoise + Fly health checks need a sensible setting:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Django's ModelBackend keeps username/password login working (admin needs it);
# allauth's backend handles social login + lets you log in by email too.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# --- django-allauth ---
ACCOUNT_ADAPTER = "arena.adapters.HotTipsAccountAdapter"
SOCIALACCOUNT_ADAPTER = "arena.adapters.HotTipsSocialAccountAdapter"
# No self-service email signups: every new account must come through Discord.
# Admins can still create local users in /admin/auth/user/.
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_RATE_LIMITS = {"login_failed": "5/5m"}
# One click: don't show the "Continue with Discord?" intermediate page.
SOCIALACCOUNT_LOGIN_ON_GET = True
# Don't show an "edit your profile" form before creating the account from
# social data; we trust the provider and write straight through.
SOCIALACCOUNT_AUTO_SIGNUP = True

# Provider credentials. Configuring an APP dict here means allauth uses these
# instead of consulting the django_site / socialapp tables; no admin-side
# wiring required.
DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")

SOCIALACCOUNT_PROVIDERS: dict = {}
if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET:
    SOCIALACCOUNT_PROVIDERS["discord"] = {
        "SCOPE": ["identify", "email"],
        "APP": {
            "client_id": DISCORD_CLIENT_ID,
            "secret": DISCORD_CLIENT_SECRET,
            "key": "",
        },
    }

# Exposed to templates so the login page can render only the buttons whose
# providers are actually configured.
ENABLED_SOCIAL_PROVIDERS = sorted(SOCIALACCOUNT_PROVIDERS.keys())

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}
