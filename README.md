# quiniela-v2

A football prediction pool portal built for the **2026 FIFA World Cup**. Users predict match results for all 103 matches (72 group stage + 31 knockout), compete on a live leaderboard, and have their scores recalculated automatically as official results come in.

## Features

- **Full bracket prediction** — predict all group stage matches upfront, then build your knockout bracket from your own predicted standings
- **FIFA tiebreaker algorithm** — group standings use the official head-to-head → overall GD/GF → FIFA ranking criteria
- **Live standings** — predicted group standings update in real time as you enter scores (HTMX, no page reloads)
- **Champion & top scorer picks** — locked together with all predictions at submission time
- **Async score recalculation** — admin enters an official result → Celery task recalculates points for every prediction across all pools
- **Multiple pools** — one tournament can have many pools; users can belong to multiple pools
- **Configurable scoring** — point values set per pool (or inherited from tournament defaults)
- **Leaderboard** — dense ranking with 60-second auto-refresh

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| Framework | Django 5.x |
| Frontend | Django templates + HTMX + Tailwind CSS (CDN) |
| Database | PostgreSQL (production) / SQLite (development) |
| Async tasks | Celery 5 + Redis |
| Static files | WhiteNoise |
| Hosting | Railway.app |
| Package manager | `uv` |

## Project Structure

```
quiniela-v2/
├── apps/
│   ├── core/           # Health check endpoint
│   ├── users/          # Custom User model (email login, nickname)
│   ├── tournaments/    # Tournament, Team, Match models + FIFA standings algorithm
│   ├── pools/          # Pool, PoolMembership, Prediction, champion/top scorer picks
│   ├── predictions/    # Prediction views (group stage + knockout + submission)
│   └── leaderboard/    # LeaderboardEntry, scoring logic, Celery tasks
├── data/
│   ├── wc2026.json     # 48 teams, 12 groups (seed data)
│   └── r32_bracket.json # FIFA R32 slot assignment table
├── quiniela/
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py    # SQLite + DEBUG, Celery eager mode for tests
│   │   └── production.py
│   └── celery.py
├── templates/
├── tests/              # 115 tests
├── railway.toml
└── start.sh            # Routes web vs. Celery worker via RAILWAY_SERVICE_NAME
```

## Getting Started

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync

# Set up local environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY

# Run migrations (uses SQLite locally)
uv run manage.py migrate

# Seed 2026 FIFA World Cup data (48 teams, 12 groups, 72 matches)
uv run manage.py load_wc2026

# Create a superuser
uv run manage.py createsuperuser

# Start the dev server
uv run manage.py runserver
```

For async score recalculation (optional in development — tasks run eagerly in tests):

```bash
# In a separate terminal
celery -A quiniela worker --loglevel=info
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Django secret key |
| `DATABASE_URL` | ✅ prod | PostgreSQL connection string (auto-set by Railway) |
| `REDIS_URL` | ✅ prod | Redis connection string (auto-set by Railway) |
| `ALLOWED_HOSTS` | ✅ prod | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | ✅ prod | Comma-separated origins (required for HTMX POSTs) |
| `DEBUG` | — | `False` in production |
| `DJANGO_SETTINGS_MODULE` | — | Defaults to `quiniela.settings.local` |

See `.env.example` for a full template.

## Running Tests

```bash
uv run pytest                          # all 115 tests
uv run pytest tests/test_standings.py  # FIFA standings algorithm only
uv run pytest -k "test_three_way_tie"  # single test by name
uv run ruff check .                    # lint
uv run mypy .                          # type check
```

## Scoring System

Default point values (configurable per pool via `scoring_config` JSON):

| Event | Points |
|---|---|
| Exact score | 3 |
| Correct result (win/draw/loss) | 1 |
| Correct penalty winner (knockout) | 1 |
| Tournament champion | 5 |
| Top scorer | 3 |

Scoring is defined in `apps/leaderboard/scoring.py` as pure Python functions with no Django dependencies — easy to test and override.

## Deployment (Railway)

The project uses two Railway services from the same repository:

| Service | Start command |
|---|---|
| `web` | `gunicorn quiniela.wsgi:application --workers 2 --bind 0.0.0.0:$PORT` |
| `celery` | `celery -A quiniela worker --loglevel=info --concurrency=2` |

`start.sh` routes automatically based on Railway's `RAILWAY_SERVICE_NAME` environment variable — no manual `SERVICE_TYPE` configuration needed.

Migrations run via `releaseCommand` in `railway.toml` (after build, before the new deploy goes live). Static files are collected at build time and served by WhiteNoise.

After deploying, seed the database via the Railway shell:

```bash
python manage.py load_wc2026
python manage.py createsuperuser
```

## Key Domain Concepts

- **Tournament** — a competition (e.g., WC2026). Holds teams, matches, and a default scoring config.
- **Pool** — a prediction contest tied to one tournament. Multiple pools per tournament; users can join many pools.
- **Prediction** — one user's scoreline prediction for one match within one pool. Locked on submission.
- **Submission** — when a user confirms their champion + top scorer picks, all predictions are permanently locked.
- **LeaderboardEntry** — denormalized total points per user per pool. Recalculated by Celery whenever an official result is saved by the admin.
