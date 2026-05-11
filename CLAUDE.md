# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`quiniela-v2` is a football prediction pool portal. Users predict match results for tournaments and compete on a leaderboard. Primary focus: 2026 FIFA World Cup. Designed to generalize to any football competition.

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| Web framework | Django 5.x |
| Frontend | Django templates + HTMX + Tailwind CSS |
| Database | PostgreSQL (prod) / SQLite (dev) |
| Async tasks | Celery + Redis |
| Hosting | Railway.app |
| Package manager | `uv` |

## Commands

Once `pyproject.toml` is set up, standard commands will be:

```bash
uv run manage.py runserver          # dev server
uv run manage.py migrate            # apply migrations
uv run manage.py makemigrations     # generate migrations
uv run pytest                       # run all tests
uv run pytest tests/path/test_x.py  # run a single test file
uv run ruff check .                 # lint
uv run ruff format .                # format
uv run mypy .                       # type check
celery -A quiniela worker -l info   # start Celery worker
```

## Architecture

Monolith Django application. No separate frontend service.

```
quiniela-v2/
├── quiniela/          # Django project config (settings/, urls.py, celery.py)
├── apps/
│   ├── users/         # Custom user model (nickname, first/last name, email)
│   ├── tournaments/   # Tournament, Team, TournamentTeam, Match models
│   ├── pools/         # Pool, PoolMembership, Prediction, Champion/TopScorer picks
│   ├── leaderboard/   # LeaderboardEntry, scoring logic, async recalculation task
│   └── admin_panel/   # Custom admin views beyond Django admin
├── templates/
└── tests/
```

### Key domain concepts

- **Tournament**: a competition (e.g., 2026 FIFA World Cup). Has groups, teams, matches, and a scoring config.
- **Pool**: a prediction contest tied to one tournament. Multiple pools can exist per tournament; a user can join multiple pools.
- **Prediction**: one user's predicted scoreline for one match, within one pool. Locked when the user submits (sets `PoolMembership.predictions_submitted = True`).
- **LeaderboardEntry**: denormalized points per user per pool. Recalculated asynchronously (Celery) whenever an official result is entered.

### Critical algorithm: group standings tiebreaker

The FIFA tiebreaker for tied teams applies head-to-head criteria first (points → GD → GF among tied teams only), then overall group criteria (GD → GF → conduct score → FIFA ranking). This is implemented as a pure Python function in `apps/tournaments/standings.py` and must be heavily unit-tested. See research doc for full tiebreaker order.

### Async score recalculation flow

Admin enters official result → `post_save` signal on `Match` → Celery task `recalculate_pool_scores(match_id)` → updates `Prediction.points_awarded` for all predictions of that match → recalculates `LeaderboardEntry` per pool.

## Research

Full architecture research (domain model, feasibility, FIFA rules): `thoughts/miguel/research/2026-05-08-quiniela-project-architecture.md`
