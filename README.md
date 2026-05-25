# Hot Tips

Arena Hot Tips tool — a small trusted-user web app where players collaboratively log fixed "hot tips" for the day's arena matches and see calculated win percentages update live.

See [`SPEC.md`](SPEC.md) for the full product spec.

Tech: Django 5.2 + DRF backend, React 19 + Vite 6 + TypeScript frontend, SQLite, packaged as a single Docker image for production.

## Prerequisites

You need exactly one thing installed:

- **Docker** (with Compose v2; bundled with modern Docker installs).

That's it. Python, Node, npm, and uv all live inside the containers.

For deployment, you'll additionally want:

- **flyctl** — only when you're ready to deploy. `curl -L https://fly.io/install.sh | sh`

## Dev (Docker)

Bring up both the Django backend (port 8000) and the Vite dev server (port 5173):

```bash
docker compose up
```

Then visit:

- <http://localhost:5173/> — the React app (proxies API/admin/accounts to the backend)
- <http://localhost:8000/admin/> — Django admin
- <http://localhost:8000/accounts/login/> — login form

### First-time setup inside the running stack

In another shell, run:

```bash
docker compose exec backend uv run python manage.py createsuperuser
docker compose exec backend uv run python manage.py seed_arena
```

`seed_arena` is idempotent and inserts the 7 fighters, 21 matchups, and 56 derived tip definitions.

### Useful dev commands

```bash
docker compose exec backend uv run pytest            # run the test suite
docker compose exec backend uv run python manage.py shell
docker compose exec backend uv run python manage.py makemigrations
docker compose down                                  # stop everything
docker compose down -v                               # also wipe the dev SQLite DB and node_modules volume
```

### Onboarding new users (Discord OAuth + admin approval)

The primary path is "user signs in with Discord, admin approves them":

1. User visits the site and clicks **Sign in with Discord** on `/accounts/login/`.
2. They authorize on Discord and get redirected back.
3. Their account is created with `is_active=False`, and they see the **Awaiting approval** page.
4. You (admin) open <http://localhost:8000/admin/auth/user/> — the list defaults to **Pending approval**, so you see the new signup at the top.
5. Tick the user, choose **Approve selected users (set Active)** from the actions menu, click **Go**.
6. The user reloads `/` and they're in.

No emails, no password-set links, no manual user creation.

If for some reason you need a local username/password account (e.g. a non-OAuth admin), use the standard **Add user** form at `/admin/auth/user/add/` — it works the normal Django way (set a password, mark `is_active=True`, optionally `is_staff=True`).

### Setting up the Discord OAuth app

A single Discord OAuth app can serve both dev and prod (you just list multiple redirect URIs on it).

1. Go to <https://discord.com/developers/applications> and click **New Application**. Name it "Hot Tips".
2. In the left sidebar, open **OAuth2**.
3. Under **Redirects**, click **Add Another** for each environment you want:
   - `http://localhost:5173/accounts/discord/login/callback/` (dev, via Vite)
   - `https://your-app.fly.dev/accounts/discord/login/callback/` (prod — replace with your actual Fly hostname)
4. Copy **Client ID**. Click **Reset Secret** to reveal **Client Secret**.

#### Wiring credentials into dev

Drop this into a `.env` next to `compose.yml` (read automatically by `docker compose`):

```dotenv
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
```

Then `docker compose down && docker compose up` and the Discord button appears on `/accounts/login/`.

#### Wiring credentials into Fly

```bash
fly secrets set \
    DISCORD_CLIENT_ID="..." \
    DISCORD_CLIENT_SECRET="..."
```

## Production build (local sanity check)

```bash
DJANGO_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(50))") \
docker compose -f compose.prod.yml up --build
```

Then hit <http://localhost:8000/>. The built React bundle is served by Django + WhiteNoise; gunicorn handles requests; SQLite lives in a named Docker volume so data survives container restarts.

## Deploying to Fly.io

The image already targets `prod` and works on a 256 MB shared-CPU Fly machine. One-time setup:

```bash
fly launch --no-deploy --name hot-tips --region <closest-region>
fly volumes create hot_tips_data --size 1 --region <same-region>
fly secrets set \
    DJANGO_SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(50))')" \
    DJANGO_ALLOWED_HOSTS="hot-tips.fly.dev" \
    DJANGO_CSRF_TRUSTED="https://hot-tips.fly.dev" \
    DISCORD_CLIENT_ID="..." \
    DISCORD_CLIENT_SECRET="..."
fly deploy
```

After the first deploy:

```bash
fly ssh console -C "uv run python manage.py createsuperuser"
fly ssh console -C "uv run python manage.py seed_arena"
```

Subsequent code changes deploy with just `fly deploy`.

### Backups

The whole database is one file at `/data/db.sqlite3` on the Fly volume. Quick backup:

```bash
fly ssh console -C "cat /data/db.sqlite3" > backups/db-$(date +%F).sqlite3
```

## Project layout

```
hot-tips/
├── SPEC.md
├── README.md
├── Dockerfile           # multi-stage: frontend-build, frontend-dev, backend-base, backend-dev, prod
├── compose.yml          # dev (default)
├── compose.prod.yml     # local prod-image sanity check
├── fly.toml             # Fly.io deploy config
├── .dockerignore
├── .gitignore
├── backend/
│   ├── pyproject.toml   # uv-managed deps
│   ├── manage.py
│   ├── hot_tips/        # Django project (settings, urls, wsgi, asgi)
│   ├── arena/           # main app (models, views, services, seed, tests)
│   └── templates/       # base auth templates + dev index fallback
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── main.tsx, App.tsx
        ├── api.ts, types.ts, usePolledArenaState.ts
        ├── styles.css
        └── components/  # Header, FighterTipsTab, MatchupTipsTab, MatchResultsTable, TipToggleButton
```

## Architecture notes

- **Game-day reset**: handled server-side in `arena/services.py::current_game_day` using `ZoneInfo("America/New_York")`, so it's DST-aware. The browser timezone is never trusted.
- **15-tip cap**: enforced in `arena/views.py::ToggleTipView` inside `transaction.atomic()` with `select_for_update()` on today's `DailyTipSelection` rows. Two simultaneous activations cannot push the pool past 15.
- **Audit log**: every activate/deactivate writes a `DailyTipAuditLog` row; admin lists are read-only.
- **Polling**: the frontend re-fetches `/api/arena/state/` every 10 s when the tab is visible (paused otherwise). Simple, robust, and enough for a small user base.
- **Auth**: Django session cookies + CSRF, same-origin in production (Vite proxy in dev). Social login via `django-allauth` (Discord). New signups land in `is_active=False` via a `SocialAccountAdapter` override and stay there until an admin approves them in `/admin/auth/user/`. DRF uses `SessionAuthentication` only; anonymous viewers get read-only access (no `IsAuthenticated` on `GET /api/arena/state/`).
- **Static assets**: WhiteNoise compresses and serves the built React bundle. Vite content-hashes filenames, so we use `CompressedStaticFilesStorage` (no double-hashing manifest).
