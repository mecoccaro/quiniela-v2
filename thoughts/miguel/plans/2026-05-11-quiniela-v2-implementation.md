---
date: 2026-05-11T00:00:00-03:00
planner: miguel
git_commit: 707c02168ec37f107c4523bdb9e7feac688f2d76
branch: master
repository: quiniela-v2
topic: "quiniela-v2 — full implementation plan for football prediction pool portal"
tags: [plan, django, quiniela, world-cup-2026, prediction-pool]
status: in-progress
autonomy: critical
commit_per_phase: true
last_updated: 2026-05-11
last_updated_by: miguel
---

# quiniela-v2 — Football Prediction Pool Portal Implementation Plan

## Overview

Build a full-stack Django monolith for football prediction pools ("quinielas"). Users register, get assigned to pools by an admin, predict match results for the 2026 FIFA World Cup, and compete on a leaderboard. Group standings are calculated using official FIFA tiebreaker rules. Scores are recalculated asynchronously via Celery when an admin enters official results.

- **Motivation**: Greenfield project — no existing codebase
- **Related**: [`thoughts/miguel/research/2026-05-08-quiniela-project-architecture.md`]

## Current State Analysis

Repository contains only `.gitignore`, `LICENSE`, `README.md`, and `CLAUDE.md`. No Python source code, no `pyproject.toml`, no database, no dependencies installed.

## Desired End State

A deployed Django application on Railway.app where:
- Users register (first name, last name, nickname, email, password) and are assigned to pools by an admin
- Users predict all 72 WC2026 group stage matches plus knockout rounds (R32 through Final)
- Group standings are calculated from user predictions using the FIFA tiebreaker algorithm (head-to-head → overall GD/GF → FIFA ranking)
- The 8 best third-place teams are ranked cross-group; R32 bracket slots assigned via FIFA's pre-defined lookup table
- Knockout predictions include 90-min scoreline + penalty winner (when a draw is predicted)
- Predictions are locked when a user confirms champion + top scorer picks
- Admin enters official results → Celery asynchronously recalculates points for all pool members
- Leaderboard ranks all pool members by total accumulated points

## What We're NOT Doing

- Mobile app or native client — web browser only
- Real-time live match tracking or automatic score scraping from external APIs
- Social login (OAuth / Google) — email + password only for MVP
- Payment or prize management
- Email notifications (post-MVP)
- Multi-language / i18n framework
- Card/conduct tracking for tiebreakers — FIFA ranking used as final criterion
- Pluggable tiebreaker strategy for non-World-Cup competitions (post-MVP)

## Design Decisions

| Decision | Choice |
|---|---|
| Knockout prediction | 90-min score + pens/ET winner (only when draw predicted) |
| Pool join | Admin assigns users directly in admin panel |
| Match prediction lock | Only when user submits (confirms champion + top scorer) |
| Conduct/card tracking | Skipped — FIFA ranking as final tiebreaker |
| Data seeding | Management command + bundled JSON fixture |
| Scoring points | Configurable JSON per pool; exact values TBD before launch |
| Top scorer pick | Free-text player name (no Player FK table for MVP) |
| Generalization | World Cup-specific; pluggable strategy post-MVP |

## Implementation Approach

- Custom `AbstractUser` with `nickname` field — set before first migration, never change
- All domain models in two Django apps: `tournaments` (match/team/bracket data) and `pools` (user predictions and scores)
- Pure Python function for group standings — zero Django dependencies, unit-tested in isolation
- HTMX drives all live interactions (standings, prediction saving, leaderboard); no JavaScript framework
- Celery task triggered via `post_save` signal on `Match`; tasks are idempotent (safe to re-run)
- Admin panel uses Django admin with custom `ModelAdmin` classes; no separate admin frontend
- Phases 1–4 are pure foundation (no UI beyond auth); Phases 5–9 are feature layers; Phase 10 deploys

## Quick Verification Reference

```bash
uv run pytest                          # all tests
uv run pytest tests/test_standings.py  # single file
uv run pytest -k "test_three_way_tie"  # single test
uv run ruff check .                    # lint
uv run ruff format --check .           # format check
uv run mypy .                          # type check
uv run manage.py runserver             # dev server
celery -A quiniela worker -l info      # Celery worker (separate terminal)
uv run manage.py load_wc2026          # seed WC2026 data
```

---

## Phase 1: Project Bootstrap

### Overview

A working Django 5.x project scaffolded with `uv`, custom `User` model, split settings (base/local/production), Celery skeleton, ruff/mypy/pytest configured, and a health check endpoint returning HTTP 200. Running `uv run manage.py migrate` succeeds against SQLite locally.

### Changes Required:

#### 1. Package manifest
**File**: `pyproject.toml`
**Changes**: Create with Django 5.x, psycopg[binary], celery[redis], gunicorn, whitenoise, dj-database-url as runtime deps; ruff, mypy, django-stubs, pytest, pytest-django, factory-boy as dev deps. Set `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` sections.

#### 2. Django project scaffold
**Files**: `manage.py`, `quiniela/__init__.py`, `quiniela/settings/__init__.py`, `quiniela/settings/base.py`, `quiniela/settings/local.py`, `quiniela/settings/production.py`, `quiniela/urls.py`, `quiniela/wsgi.py`, `quiniela/asgi.py`
**Changes**: Create full Django project. `base.py` defines `INSTALLED_APPS`, `AUTH_USER_MODEL = "users.User"`, `LANGUAGE_CODE = "es"`, `TIME_ZONE = "America/Buenos_Aires"`. `local.py` uses SQLite and `DEBUG=True`. `production.py` reads all config from env vars via `os.environ`.

#### 3. Custom User model
**File**: `apps/users/models.py`
**Changes**: `User(AbstractUser)` adding `nickname = models.CharField(max_length=50, unique=True)`. Use email as `USERNAME_FIELD` (set `username` as unused). Register in `apps/users/admin.py`.

#### 4. Celery skeleton
**File**: `quiniela/celery.py`
**Changes**: Standard Django Celery app init. Wire `quiniela/__init__.py` to import `celery_app`. No tasks yet.

#### 5. Health check
**Files**: `quiniela/urls.py` (add route), `apps/core/views.py`
**Changes**: `GET /health/` returns `JsonResponse({"status": "ok"})`. No auth required.

#### 6. Environment template
**File**: `.env.example`
**Changes**: Document `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_HOSTS`, `DEBUG`.

#### 7. Test config
**File**: `conftest.py` (project root)
**Changes**: `pytest.ini_options` pointed at `quiniela.settings.local`. `@pytest.fixture` for `db` access via `pytest-django`.

#### 8. AppConfig setup for `apps/` subdirectory
**Files**: `apps/users/apps.py`, `apps/tournaments/apps.py`, `apps/pools/apps.py`, `apps/leaderboard/apps.py`, `apps/predictions/apps.py`, `apps/core/apps.py`
**Changes**: Each app needs `AppConfig` with `name = "apps.<appname>"` (e.g. `name = "apps.users"`). `INSTALLED_APPS` in `base.py` uses the full dotted config path (e.g. `"apps.users.apps.UsersConfig"`). Without this, Django cannot discover models or signals under the `apps/` directory structure.

#### 9. Celery test settings
**File**: `quiniela/settings/local.py`
**Changes**: Add `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True`. This makes Celery tasks run synchronously in tests (Phases 2–8) without requiring a running Redis broker. Must be set from Phase 1 so any imported Celery config doesn't break tests.

### Success Criteria:

#### Automated Verification:
- [x] `uv run manage.py migrate` exits 0 with no errors
- [x] `DJANGO_SETTINGS_MODULE=quiniela.settings.production uv run manage.py check --deploy` reports no critical errors (must run against production settings — `--deploy` will always warn on local/DEBUG=True)
- [x] `uv run ruff check .` exits 0
- [x] `uv run mypy .` exits 0
- [x] `uv run pytest` exits 0 (at minimum the health check view test passes)

#### Automated QA:
- [ ] `uv run manage.py runserver` starts and `curl http://localhost:8000/health/` returns `{"status": "ok"}`
- [ ] `uv run manage.py createsuperuser` (non-interactively via env vars) succeeds and admin login at `/admin/` works

#### Manual Verification:
- [ ] `/admin/` login page loads without 500 errors

**Implementation Note**: After this phase, pause for manual confirmation. Once verified, commit: `[phase 1] project bootstrap — Django scaffold, custom user model, tooling`.

---

## Phase 2: Tournament & Pool Domain Models

### Overview

All domain models defined, migrated, and registered in Django admin. Running `uv run manage.py migrate` produces a clean schema with all tables. No views or templates yet.

### Changes Required:

#### 1. Tournament app models
**File**: `apps/tournaments/models.py`
**Changes**:

```
Tournament:
  name (str, 100), slug (unique), status (choices: upcoming/group_stage/knockout/completed)
  num_groups (int, default=12), teams_per_group (int, default=4)
  third_place_advancers (int, default=8), scoring_config (JSONField, default=dict)

Team:
  name (str, 100), fifa_code (CharField 3, unique), flag_url (URLField, blank)

TournamentTeam:
  tournament (FK), team (FK), group_letter (CharField 1, e.g. "A")
  fifa_ranking (PositiveIntegerField)
  unique_together: (tournament, team)

Match:
  tournament (FK), stage (choices: group/r32/r16/qf/sf/third_place/final)
  group_letter (CharField 1, blank/null — group matches only)
  home_team (FK Team), away_team (FK Team)
  scheduled_at (DateTimeField, null/blank)
  home_score (PositiveIntegerField, null/blank)   # official 90-min result
  away_score (PositiveIntegerField, null/blank)   # official 90-min result
  knockout_winner (FK Team, null/blank, related_name="knockout_wins")  # set when ET/pens decide
  status (choices: scheduled/live/completed, default=scheduled)
  # No unique_together on Match — teams can meet twice (group stage + knockout rematch is valid)
  # Use a database index on (tournament, stage, group_letter) for query performance instead
```

#### 2. Pools app models
**File**: `apps/pools/models.py`
**Changes**:

```
Pool:
  name (str, 100), tournament (FK), status (choices: open/locked/completed)
  lock_deadline (DateTimeField, null/blank)
  scoring_config (JSONField, null/blank)  # overrides tournament.scoring_config if set

PoolMembership:
  pool (FK), user (FK users.User)
  joined_at (DateTimeField, auto_now_add)
  predictions_submitted (BooleanField, default=False)
  unique_together: (pool, user)

Prediction:
  user (FK users.User), pool (FK), match (FK tournaments.Match)
  predicted_home_score (PositiveIntegerField)
  predicted_away_score (PositiveIntegerField)
  predicted_winner (FK Team, null/blank)  # knockout only: team that wins pens if draw predicted
  points_awarded (IntegerField, null/blank)
  unique_together: (user, pool, match)

PoolChampionPick:
  user (FK users.User), pool (FK)
  team (FK tournaments.Team)
  points_awarded (IntegerField, null/blank)
  unique_together: (user, pool)

PoolTopScorerPick:
  user (FK users.User), pool (FK)
  player_name (CharField 100)
  points_awarded (IntegerField, null/blank)
  unique_together: (user, pool)

LeaderboardEntry:
  pool (FK), user (FK users.User)
  total_points (IntegerField, default=0)
  rank (PositiveIntegerField, default=0)
  last_calculated_at (DateTimeField, null/blank)
  unique_together: (pool, user)
```

#### 3. Migrations
**Files**: `apps/tournaments/migrations/0001_initial.py`, `apps/pools/migrations/0001_initial.py`
**Changes**: Generated via `makemigrations`. Both apps listed in `INSTALLED_APPS`.

#### 4. Admin registrations
**Files**: `apps/tournaments/admin.py`, `apps/pools/admin.py`
**Changes**: Register all models with `@admin.register`. `MatchAdmin` includes `list_display = ["tournament", "stage", "home_team", "away_team", "status", "home_score", "away_score"]`. `PoolAdmin` includes inline `PoolMembershipInline`.

#### 5. Model tests
**File**: `tests/test_models.py`
**Changes**: Basic model creation tests (Tournament, Match, Pool, Prediction) asserting `__str__`, unique constraints, and FK integrity.

### Success Criteria:

#### Automated Verification:
- [x] `uv run manage.py migrate` exits 0
- [x] `uv run manage.py check` exits 0
- [x] `uv run pytest tests/test_models.py` passes
- [x] `uv run ruff check .` exits 0
- [x] `uv run mypy .` exits 0

#### Automated QA:
- [ ] All models visible in `/admin/` with correct fields
- [ ] Creating a `Tournament → Pool → PoolMembership` chain in admin succeeds without errors

#### Manual Verification:
- [ ] Schema looks correct in Django admin (no missing fields, correct dropdowns for choice fields)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 2] domain models — Tournament, Match, Pool, Prediction, LeaderboardEntry`.

---

## Phase 3: WC2026 Data Seed & Auth UI

### Overview

Running `uv run manage.py load_wc2026` loads the 2026 FIFA World Cup fixture (48 teams, 12 groups, 72 scheduled group matches) into the database. Users can register with first name, last name, nickname, and email, and log in. Base template uses Tailwind CSS CDN and HTMX CDN.

### Changes Required:

#### 1. WC2026 JSON fixture
**File**: `data/wc2026.json`
**Changes**: Create fixture with structure:
```json
{
  "tournament": { "name": "2026 FIFA World Cup", "slug": "wc2026", ... },
  "teams": [
    { "name": "Argentina", "fifa_code": "ARG", "fifa_ranking": 1 },
    ...48 teams total...
  ],
  "groups": {
    "A": ["team_code1", "team_code2", "team_code3", "team_code4"],
    ...12 groups...
  },
  "matches": [
    { "home": "ARG", "away": "CAN", "group": "A", "scheduled_at": "2026-06-11T18:00:00-05:00" },
    ...72 group matches...
  ]
}
```
Populate from official WC2026 draw results and published schedule. FIFA rankings from official pre-tournament list.

#### 2. Load management command
**File**: `apps/tournaments/management/commands/load_wc2026.py`
**Changes**: `BaseCommand` that reads `data/wc2026.json`, creates `Tournament`, `Team`, `TournamentTeam`, and `Match` records using `get_or_create`. Idempotent — safe to re-run. Prints progress. Example: `uv run manage.py load_wc2026 [--tournament-slug wc2026]`.

#### 3. R32 bracket lookup table fixture
**File**: `data/r32_bracket.json`
**Changes**: Encode FIFA's pre-defined table mapping which 8 groups produced the advancing third-place teams → specific R32 slot assignments. Used in Phase 6 to build predicted knockout brackets. Structure:
```json
{
  "slots": {
    "R32_1": { "home": "A1", "away": "B2" },
    "R32_2": { "home": "C1", "away": "D2" },
    ...
  },
  "third_place_assignments": {
    "ABCD": { "slot": "R32_X", "...": "..." },
    ...
  }
}
```

#### 4. Base templates and static config
**Files**: `templates/base.html`, `templates/partials/nav.html`
**Changes**: `base.html` loads Tailwind CSS via CDN and HTMX via CDN in `<head>`. Navigation shows login/register when unauthenticated, username + logout when authenticated. `TEMPLATES` setting points to `templates/` dir.

#### 5. User registration & auth views
**Files**: `apps/users/forms.py`, `apps/users/views.py`, `apps/users/urls.py`
**Changes**:
- `RegistrationForm(UserCreationForm)` with fields: `first_name`, `last_name`, `nickname`, `email`, `password1`, `password2`
- `RegisterView` (CreateView): creates User, logs in, redirects to dashboard
- Wire Django's built-in `LoginView` and `LogoutView` from `django.contrib.auth.views`
- Simple dashboard view showing user's pool memberships

#### 6. Auth templates
**Files**: `templates/users/register.html`, `templates/users/login.html`, `templates/users/dashboard.html`
**Changes**: Forms styled with Tailwind utility classes. Dashboard lists pools the user belongs to with link to their prediction form.

### Success Criteria:

#### Automated Verification:
- [x] `uv run manage.py load_wc2026` exits 0
- [x] Re-running `uv run manage.py load_wc2026` exits 0 (idempotency)
- [x] `uv run pytest tests/test_seeding.py` passes: asserts 48 teams, 12 TournamentTeams per group letter, 72 matches, all with stage=`group`
- [x] `uv run pytest tests/test_auth.py` passes: registration creates user, login returns 200, logout clears session
- [x] `uv run ruff check .` and `uv run mypy .` exit 0

#### Automated QA:
- [ ] Register a test user via the form at `/users/register/` and verify redirect to dashboard
- [ ] Log in at `/users/login/` and verify nav shows username

#### Manual Verification:
- [ ] Check `/admin/tournaments/match/?stage=group` shows 72 matches correctly grouped
- [ ] Registration form shows validation errors for duplicate nickname or email

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 3] WC2026 data seed + user registration and auth`.

---

## Phase 4: Group Standings Algorithm

### Overview

A pure Python module `apps/tournaments/standings.py` implementing the FIFA group standings algorithm with full tiebreaker logic. A companion `rank_third_place_teams()` function ranks the 12 third-place finishers to identify the 8 that advance. Comprehensive unit tests cover 2-way, 3-way, and 4-way tie edge cases.

### Changes Required:

#### 1. Standings calculation module
**File**: `apps/tournaments/standings.py`
**Changes**: Define dataclasses and functions:

```python
@dataclass
class MatchResult:
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int

@dataclass
class TeamStanding:
    team_id: int
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    position: int  # 1-4 (set after all tiebreakers resolved)

def calculate_group_standings(
    matches: list[MatchResult],
    fifa_rankings: dict[int, int],  # team_id → ranking (lower = better)
) -> list[TeamStanding]:
    """Apply FIFA tiebreaker rules to produce final standings for one group."""
    ...

def rank_third_place_teams(
    third_place_teams: list[TeamStanding],
    fifa_rankings: dict[int, int],
) -> list[TeamStanding]:
    """Rank all 12 third-place teams to identify best 8 advancing to R32."""
    ...
```

**Tiebreaker order implemented** (simplified — no conduct as decided):
1. Points in H2H matches among tied teams
2. Goal difference in H2H matches among tied teams
3. Goals scored in H2H matches among tied teams
4. *(Apply 1–3 again to the remaining subset still tied)*
5. Overall goal difference in group
6. Overall goals scored in group
7. FIFA ranking (lower number wins)

**Third-place cross-group ranking criteria:**
1. Points, 2. GD, 3. GF, 4. FIFA ranking

#### 2. Unit test suite
**File**: `tests/test_standings.py`
**Changes**: Comprehensive tests including:
- Normal case (no ties): all 4 teams on different points
- 2-way tie resolved by H2H GD
- 2-way tie resolved by H2H GF
- 2-way tie resolved by overall GD
- 2-way tie resolved by FIFA ranking (last resort)
- 3-way tie: H2H resolves two, overall GD resolves third
- 3-way tie: fully resolved by FIFA ranking
- 4-way tie (all teams same points, same GD, same GF)
- `rank_third_place_teams()`: correct ordering of 12 teams by points then GD then GF then FIFA ranking

#### 3. Integration helper
**File**: `apps/tournaments/services.py`
**Changes**: `get_predicted_group_standings(user, pool, group_letter)` — fetches user's Predictions for a group's 6 matches, converts to `MatchResult` list, calls `calculate_group_standings()`, returns `list[TeamStanding]`. Used by Phase 5 views.

#### 4. Integration helper tests
**File**: `tests/test_services.py`
**Changes**: `@pytest.mark.django_db` test for `get_predicted_group_standings()`: create Tournament + 4 Teams + 6 Matches + 6 Predictions for one group, call the helper, assert the returned standings are ordered correctly. Verifies the DB-to-pure-function bridge works end-to-end.

### Success Criteria:

#### Automated Verification:
- [x] `uv run pytest tests/test_standings.py -v` passes all test cases (target: ≥ 20 test cases)
- [x] `uv run pytest tests/test_standings.py --tb=short` exits 0 with 0 failures
- [x] `uv run mypy apps/tournaments/standings.py` exits 0 (fully typed)
- [x] `uv run ruff check .` exits 0

#### Automated QA:
- [ ] Run `uv run pytest tests/test_standings.py -v` and verify edge cases are explicitly named in output (e.g., `test_three_way_tie_resolved_by_h2h_gd`)

#### Manual Verification:
- [ ] Review test cases against the official FIFA tiebreaker rules page to confirm all 7 criteria are correctly ordered

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 4] FIFA group standings tiebreaker algorithm + unit tests`.

---

## Phase 5: Group Stage Prediction UI

### Overview

Logged-in users assigned to a pool can access a prediction form for all 72 group stage matches, organized by group (A–L). As they enter scores, HTMX updates the predicted group standings for that group in real time. Progress is shown (how many matches have predictions vs. 72 total).

### Changes Required:

#### 1. Prediction views (group stage)
**File**: `apps/predictions/views.py`
**Changes**:
- `GroupPredictionsView`: renders all 12 groups with their matches and any existing predictions for the logged-in user + pool
- `SaveMatchPredictionView` (HTMX endpoint): `POST /predictions/pool/<pool_id>/match/<match_id>/` — saves/updates a single match prediction, returns updated standings partial for that group via HTMX response
- Both views require login and pool membership; raise 403 if predictions already submitted

#### 2. Forms
**File**: `apps/predictions/forms.py`
**Changes**: `MatchPredictionForm` with `predicted_home_score` and `predicted_away_score` (IntegerField, min=0, max=20). Validation: both must be provided together.

#### 3. URL configuration
**File**: `apps/predictions/urls.py`, `quiniela/urls.py`
**Changes**: Wire prediction URLs under `/predictions/`. Include in root `urls.py`.

#### 4. Group predictions template
**Files**: `templates/predictions/group_stage.html`, `templates/predictions/partials/group_standings.html`
**Changes**: `group_stage.html` renders accordion/tab per group (A–L). Each group shows: 6 match cards with score input fields (pre-filled if prediction exists), and the `group_standings` partial. `group_standings.html` is the HTMX target — shows a 4-row standings table (position, team, P, W, D, L, GF, GA, GD, Pts) computed from current predictions. Qualifying positions highlighted (1st/2nd = green, 3rd = orange if likely advancing, 4th = red).

#### 5. Progress indicator
**Changes**: In `group_stage.html`, show `X / 72 matches predicted`. Computed in view by counting non-null Predictions for the user+pool. Use HTMX `hx-indicator` for saving state.

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/test_prediction_views.py` passes: authenticated user can GET the group stage page (200), POST a prediction for a match (201/200), re-POST updates existing prediction (200)
- [ ] Test: unauthenticated user redirected to login (302)
- [ ] Test: user with `predictions_submitted=True` gets 403 on POST
- [ ] `uv run ruff check .` and `uv run mypy .` exit 0

#### Automated QA:
- [ ] Start dev server, load WC2026 data, create user + pool membership, open `/predictions/pool/1/group-stage/` — verify all 12 groups render with 6 matches each
- [ ] Enter a score for one match via HTMX and verify the standings partial updates without full page reload (check Network tab shows partial HTML response)

#### Manual Verification:
- [ ] Enter all 6 match scores for Group A and verify that the standings table orders teams correctly (spot-check against manual calculation)
- [ ] Progress indicator increments from 0 to 6 after entering Group A predictions

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 5] group stage prediction UI with live standings via HTMX`.

---

## Phase 6: Knockout Predictions, Champion Pick & Submission Lock

### Overview

This is an **upfront bracket-prediction system**: users predict all 103 matches (72 group + 31 knockout) before locking, based entirely on their own predicted bracket — not on actual results. After entering all 72 group stage predictions, knockout round matchups are derived from the user's *own predicted group standings* (not official results). Users work through R32 → R16 → QF → SF → Final, with each round's matchups derived from their previous-round predictions. Once all knockout predictions are entered, users select a tournament champion and enter a top scorer name. Confirming these final picks locks all predictions permanently. Official results entered by the admin later determine points, but users cannot modify predictions at that point.

### Changes Required:

#### 1. Knockout prediction views
**File**: `apps/predictions/views.py` (extend)
**Changes**:
- `KnockoutPredictionsView`: gated — requires all 72 group predictions entered. Builds the predicted R32 bracket from group standings + `data/r32_bracket.json` lookup. Shows one stage at a time (R32 first; subsequent rounds built from previous predictions).
- `SaveKnockoutPredictionView` (HTMX): saves `predicted_home_score`, `predicted_away_score`, and optionally `predicted_winner` (required when scores are equal for a knockout match)

#### 2. R32 bracket service
**File**: `apps/tournaments/services.py` (extend)
**Changes**: `build_predicted_r32_bracket(user, pool)` — loads user's group predictions, calls `calculate_group_standings()` for all 12 groups, calls `rank_third_place_teams()` for all 12 third-place finishers, then maps advancing teams to R32 match slots using `data/r32_bracket.json` fixture. Returns a `list[PredictedMatch]` for the R32.

#### 3. Predicted_winner validation
**File**: `apps/predictions/forms.py` (extend)
**Changes**: `KnockoutPredictionForm` — validates that if `predicted_home_score == predicted_away_score`, then `predicted_winner` is required and must be one of the two teams in the match.

#### 4. Champion and top scorer pick views
**File**: `apps/predictions/views.py` (extend)
**Changes**:
- `ChampionPickView`: shows all 48 teams as a radio-button list. Pre-selected if already saved.
- `TopScorerPickView`: shows a text input for player name. Pre-filled if saved.
- Both gated: require all group + knockout predictions entered.

#### 5. Submission confirmation view
**File**: `apps/predictions/views.py` (extend)
**Changes**: `SubmitPredictionsView` — shows a summary of champion + top scorer picks and a "Confirm and lock predictions" button. On POST: sets `PoolMembership.predictions_submitted = True`, creates `LeaderboardEntry` with `total_points=0` if not exists. Redirects to leaderboard (Phase 9).

#### 6. Templates
**Files**: `templates/predictions/knockout.html`, `templates/predictions/champion_pick.html`, `templates/predictions/top_scorer_pick.html`, `templates/predictions/submission_confirm.html`

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/test_knockout_predictions.py` passes: gating blocks access when group stage incomplete, knockout prediction saves correctly, predicted_winner validation enforced
- [ ] Test: `SubmitPredictionsView` POST sets `predictions_submitted=True` and creates `LeaderboardEntry`
- [ ] Test: any prediction POST after `predictions_submitted=True` returns 403
- [ ] `uv run ruff check .` and `uv run mypy .` exit 0

#### Automated QA:
- [ ] With all 72 group predictions entered, navigate to knockout predictions page — verify R32 matchups render using predicted group winners/runners-up
- [ ] Enter a draw prediction for a knockout match — verify `predicted_winner` dropdown appears and is required

#### Manual Verification:
- [ ] Spot-check one R32 matchup against manually calculated group standings to confirm bracket service works correctly
- [ ] Confirm submission flow: after submitting, all prediction forms render as read-only

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 6] knockout predictions, champion/top scorer picks, submission lock`.

---

## Phase 7: Admin Panel

### Overview

Admin panel extended with custom `ModelAdmin` classes: pool management (create pool, assign users), official match result entry (home/away score + knockout winner if applicable), and read-only views of all predictions and participants.

### Changes Required:

#### 1. Pool management admin
**File**: `apps/pools/admin.py` (extend)
**Changes**:
- `PoolAdmin` with `PoolMembershipInline` (tabular inline — add/remove users from pool)
- `list_display`: name, tournament, status, member count
- Action: "Lock pool" — sets status to locked for selected pools

#### 2. Match result entry admin
**File**: `apps/tournaments/admin.py` (extend)
**Changes**:
- `MatchAdmin` with custom `change_view` form: fields `home_score`, `away_score`, `status` (set to `completed`), `knockout_winner` (FK — shown only for non-group matches)
- Custom `save_model()` override: after saving, trigger `recalculate_pool_scores.delay(instance.pk)` — import the task lazily inside `save_model()` (`from apps.leaderboard.tasks import recalculate_pool_scores`) to avoid circular import. **Note**: `apps/leaderboard/tasks.py` is created in Phase 8 — Phase 7 tests must mock this import or use a try/except stub to remain runnable before Phase 8 is complete.
- `list_display`: stage, group_letter, home_team, away_team, home_score, away_score, status
- `list_filter`: stage, status, tournament

#### 4a. `score_final_picks` admin trigger
**File**: `apps/tournaments/admin.py` (extend)
**Changes**: Custom admin action on `TournamentAdmin`: "Score final picks (champion + top scorer)". Prompts admin for `official_champion_id` (FK selector) and `official_top_scorer_name` (text field) via a custom intermediate form, then calls `score_final_picks.delay(tournament_id, champion_id, top_scorer_name)`. This is the trigger for the Phase 8 `score_final_picks()` task — also imported lazily to avoid Phase 7/8 ordering issues.

#### 3. Predictions read-only admin
**File**: `apps/pools/admin.py` (extend)
**Changes**:
- `PredictionAdmin`: all fields read-only. `list_display` = user, pool, match (home vs away), predicted_home_score, predicted_away_score, points_awarded. `list_filter` = pool, user. `search_fields` = user__nickname, match__home_team__name.
- `PoolChampionPickAdmin` and `PoolTopScorerPickAdmin`: similarly read-only.

#### 4. Participant overview
**File**: `apps/pools/admin.py` (extend)
**Changes**: `PoolMembershipAdmin` with `list_display` = pool, user (nickname), predictions_submitted, joined_at. `list_filter` = pool, predictions_submitted.

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/test_admin.py` passes: admin user can GET pool list, change pool, add PoolMembership, save match result (mocked Celery call)
- [ ] `uv run ruff check .` and `uv run mypy .` exit 0

#### Automated QA:
- [ ] Log in as admin, create a Pool, add a user via `PoolMembershipInline` — verify membership created
- [ ] Enter a result for a group match (home_score=2, away_score=1, status=completed) — verify Match saved correctly

#### Manual Verification:
- [ ] Verify `list_filter` by stage and status work in MatchAdmin
- [ ] Verify PredictionAdmin is fully read-only (no save buttons)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 7] admin panel — pool management, match result entry, predictions view`.

---

## Phase 8: Async Score Engine

### Overview

Celery worker + Redis broker configured and running. When an admin saves an official match result, a `post_save` signal dispatches a Celery task that calculates points for every affected prediction across all pools and updates the leaderboard. Scoring logic is a pure Python function independent of Celery.

### Changes Required:

#### 1. Celery + Redis configuration
**Files**: `quiniela/celery.py` (update), `quiniela/settings/base.py` (update)
**Changes**: Set `CELERY_BROKER_URL` from env var `REDIS_URL` (falls back to `redis://localhost:6379/0` for local). `CELERY_RESULT_BACKEND` = same. `CELERY_TASK_SERIALIZER = "json"`. Add `celery[redis]` to `pyproject.toml` if not already present.

#### 2. Scoring logic module
**File**: `apps/leaderboard/scoring.py`
**Changes**: Pure Python functions:

```python
def score_prediction(
    predicted_home: int,
    predicted_away: int,
    official_home: int,
    official_away: int,
    stage: str,
    predicted_winner_id: int | None,
    official_knockout_winner_id: int | None,
    config: dict,
) -> int:
    """Return points awarded for one prediction."""
    ...

def get_scoring_config(pool: Pool) -> dict:
    """Return pool.scoring_config if set, else tournament.scoring_config."""
    ...
```

**Default scoring_config schema** (values TBD before launch):
```json
{
  "exact_score": 3,
  "correct_result": 1,
  "pens_winner": 1,
  "champion": 5,
  "top_scorer": 3
}
```

#### 3. Celery task
**File**: `apps/leaderboard/tasks.py`
**Changes**:

```python
@shared_task
def recalculate_pool_scores(match_id: int) -> None:
    """
    For each Prediction of this match:
      1. Calculate and save points_awarded
    Then for each affected Pool:
      2. Re-aggregate total_points from all Predictions + ChampionPick + TopScorerPick
      3. Re-rank all LeaderboardEntries in the pool
    """
```

Task is idempotent. Uses `transaction.atomic()` per pool update. Fetches all data in minimal queries using `select_related` and `prefetch_related`.

#### 4. Signal wiring
**File**: `apps/tournaments/signals.py`
**Changes**: `post_save` on `Match` — if `home_score` and `away_score` both set and `status == "completed"`: call `recalculate_pool_scores.delay(instance.pk)`.

**File**: `apps/tournaments/apps.py`
**Changes**: Import signals in `ready()`.

#### 5. Champion and top scorer scoring
**File**: `apps/leaderboard/tasks.py` (extend)
**Changes**: `score_final_picks(tournament_id: int, official_champion_id: int, official_top_scorer_name: str)` — separate task triggered by admin action after tournament ends. Sets `PoolChampionPick.points_awarded` and `PoolTopScorerPick.points_awarded` for all picks across all pools for this tournament.

#### 6. Unit tests
**File**: `tests/test_scoring.py`
**Changes**: Test `score_prediction()` for all branches: exact score (group), correct result only (group), wrong (group), knockout exact, knockout correct result, knockout pens winner bonus, knockout wrong.

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/test_scoring.py` passes: all scoring branches covered
- [ ] `uv run pytest tests/test_tasks.py` passes: task correctly updates `Prediction.points_awarded` and `LeaderboardEntry.total_points` using `@pytest.mark.django_db` — Celery runs eagerly in tests via `CELERY_TASK_ALWAYS_EAGER = True` in `local.py` (set in Phase 1); alternatively call `recalculate_pool_scores.apply(args=[match_id])` directly in tests to bypass the broker entirely
- [ ] `uv run ruff check .` and `uv run mypy .` exit 0

#### Automated QA:
- [ ] Start Celery worker (`celery -A quiniela worker -l info`); enter a match result in admin; verify in logs that `recalculate_pool_scores` task executes and completes
- [ ] Check `LeaderboardEntry.total_points` updated in database after task runs

#### Manual Verification:
- [ ] Enter result for a match that has multiple predictions; verify points awarded correctly per scoring config

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 8] async score engine — Celery task, scoring logic, leaderboard recalculation`.

---

## Phase 9: Leaderboard & Post-Submission Views

### Overview

All pool-level views available after submission: ranked leaderboard, user's own predictions (read-only), and participant overview showing other members' champion and top scorer picks.

### Changes Required:

#### 1. Leaderboard view
**File**: `apps/leaderboard/views.py`
**Changes**: `LeaderboardView` — fetches `LeaderboardEntry.objects.filter(pool=pool).order_by("rank", "user__nickname").select_related("user")`. Renders ranked table with: rank, nickname, total_points, predictions_submitted status. **Tie handling**: the `recalculate_pool_scores` task assigns the same rank to users with equal `total_points` (dense ranking: 1, 2, 2, 4 — not 1, 2, 2, 3). The leaderboard view displays tied users at the same rank value; secondary sort by `user__nickname` for stable ordering within a rank.

#### 2. My predictions view
**File**: `apps/leaderboard/views.py` (extend)
**Changes**: `MyPredictionsView` — shows user's own predictions for a pool, grouped by stage (group stage → knockout rounds). All fields read-only. Shows `points_awarded` per prediction once official results are in. Also shows their champion + top scorer pick.

#### 3. Participants overview view
**File**: `apps/leaderboard/views.py` (extend)
**Changes**: `ParticipantsView` — shows all pool members with: nickname, champion pick (team name), top scorer pick (player name), predictions_submitted status, total_points. Hides champion/top scorer pick until that user has submitted (privacy: don't show picks until locked in).

#### 4. URL config
**File**: `apps/leaderboard/urls.py`
**Changes**: Routes for `/pool/<pool_id>/leaderboard/`, `/pool/<pool_id>/my-predictions/`, `/pool/<pool_id>/participants/`. Require login.

#### 5. Templates
**Files**: `templates/leaderboard/leaderboard.html`, `templates/leaderboard/my_predictions.html`, `templates/leaderboard/participants.html`
**Changes**: Leaderboard auto-refreshes every 60 seconds via HTMX polling (`hx-trigger="every 60s"`). My predictions shows a sticky "Locked" badge when `predictions_submitted=True`.

#### 6. Dashboard update
**File**: `templates/users/dashboard.html`
**Changes**: For each pool membership, show: pool name, leaderboard rank (if available), link to predictions (if not submitted), link to leaderboard (always).

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest tests/test_leaderboard_views.py` passes: leaderboard returns 200, my-predictions returns 200, participants hides picks for non-submitted users
- [ ] Test: unauthenticated user redirected to login
- [ ] `uv run ruff check .` and `uv run mypy .` exit 0

#### Automated QA:
- [ ] With two users in a pool (one submitted, one not): leaderboard shows both; participants shows champion pick for submitted user, hides it for unsubmitted user
- [ ] HTMX polling: wait 60s on leaderboard page, verify network request fires without full page reload

#### Manual Verification:
- [ ] My predictions view displays all group + knockout predictions with correct point values shown where results exist
- [ ] Leaderboard rank matches manually computed order by total_points

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 9] leaderboard, my predictions, and participants views`.

---

## Phase 10: Production Deployment to Railway.app

### Overview

Application deployed to Railway.app with a web service (Django + gunicorn), a Celery worker service, managed PostgreSQL, and managed Redis. Environment configured via Railway's dashboard. First successful production deploy with admin accessible.

### Changes Required:

#### 1. Production settings
**File**: `quiniela/settings/production.py`
**Changes**:
```python
import dj_database_url, os
DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")
CSRF_TRUSTED_ORIGINS = os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")  # required for HTMX POSTs
DATABASES = {"default": dj_database_url.config(conn_max_age=600)}
CELERY_BROKER_URL = os.environ["REDIS_URL"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Django 5.1+ uses STORAGES dict; STATICFILES_STORAGE is deprecated
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
```
Add `CSRF_TRUSTED_ORIGINS=https://<railway-domain>` to Railway environment variables. Without this, all HTMX POST requests (prediction saves, champion pick, submission) will return 403 Forbidden in production.

#### 2. WSGI server
**File**: `pyproject.toml` (update)
**Changes**: Ensure `gunicorn` and `whitenoise` are in runtime dependencies. Add `whitenoise` to `MIDDLEWARE` (after `SecurityMiddleware`).

#### 3. Railway configuration
**File**: `railway.toml`
**Changes**:
```toml
[build]
builder = "nixpacks"
buildCommand = "uv sync && uv run manage.py collectstatic --noinput"
# Note: migrate is in releaseCommand (not buildCommand) — Railway build phase
# runs without DB access. releaseCommand runs after build, before new deploy goes live.

[deploy]
startCommand = "gunicorn quiniela.wsgi:application --workers 2 --bind 0.0.0.0:$PORT"
releaseCommand = "uv run manage.py migrate --noinput"
```

#### 4. Celery worker service
**Changes**: In Railway dashboard: add second service from same repo with start command `celery -A quiniela worker --loglevel=info --concurrency=2`. Share env vars from web service.

#### 5. Environment variables in Railway
**Changes**: Set via Railway dashboard: `SECRET_KEY`, `ALLOWED_HOSTS` (Railway-provided domain, e.g. `myapp.up.railway.app`), `CSRF_TRUSTED_ORIGINS` (e.g. `https://myapp.up.railway.app`), `DEBUG=False`, `DJANGO_SETTINGS_MODULE=quiniela.settings.production`. `DATABASE_URL` and `REDIS_URL` auto-injected by Railway services.

#### 6. Superuser creation
**Changes**: In Railway → web service → Shell: `python manage.py createsuperuser` interactively, or via management command that reads `DJANGO_SUPERUSER_*` env vars.

### Success Criteria:

#### Automated Verification:
- [x] `uv run ruff check .` and `uv run mypy .` exit 0 on final codebase
- [x] `uv run pytest` passes all tests (0 failures, 0 errors)

#### Automated QA:
- [ ] `curl https://<railway-domain>/health/` returns `{"status": "ok"}` with HTTP 200
- [ ] `curl https://<railway-domain>/admin/` returns HTTP 302 (redirect to login)
- [ ] Railway logs show no startup errors for web service
- [ ] Railway logs show Celery worker `ready` message

#### Manual Verification:
- [ ] Log in to production `/admin/` as superuser — verify all models visible
- [ ] Run `python manage.py load_wc2026` via Railway shell — verify 48 teams and 72 matches appear in admin
- [ ] Register a new user via production URL — verify redirect to dashboard

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 10] production deployment — Railway config, gunicorn, whitenoise`.

---

## Appendix

- **Follow-up plans**:
  - Scoring config values plan (decide exact_score/correct_result/champion/top_scorer point values before pools open)
  - Email notification plan (notify users when pool locks, when results are entered)
  - Competition generalization plan (pluggable tiebreaker strategy for non-WC formats)
  - Player database plan (structured Player FK for top scorer picks instead of free text)

- **Derail notes**:
  - R32 bracket lookup table is complex to encode (FIFA's pre-defined 495-combination table); may need dedicated research session before Phase 6
  - WC2026 group assignments and FIFA rankings in `data/wc2026.json` must be manually verified against official FIFA sources before seeding
  - Scoring point values intentionally left as TBD; must be decided before users start entering predictions
  - HTMX polling on leaderboard (60s) is a simplification; could upgrade to WebSocket/SSE post-MVP for real-time updates

- **References**:
  - Research: `thoughts/miguel/research/2026-05-08-quiniela-project-architecture.md`
  - FIFA WC2026 group stage rules: https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/groups-how-teams-qualify-tie-breakers
  - Railway.app docs: https://docs.railway.app
  - Django Celery integration: https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html

---

## Review Errata

_Reviewed: 2026-05-11 by Claude Code_

### Applied

- [x] **Phase 2 — `Match.unique_together` removed**: `(tournament, home_team, away_team)` constraint would block valid rematches (group + knockout). Replaced with a comment recommending a DB index instead.
- [x] **Phase 7→8 ordering — lazy import for Celery task**: `save_model()` now imports `recalculate_pool_scores` lazily inside the method body. Phase 7 tests noted as needing to mock the import before Phase 8 exists.
- [x] **Phase 7 — `score_final_picks` admin trigger added**: Custom admin action on `TournamentAdmin` defined in Phase 7 (`Changes item 4a`) to avoid this being stranded without an invocation point.
- [x] **Phase 10 — `migrate` moved to `releaseCommand`**: Railway build phase has no DB access; `migrate` must run in `releaseCommand` (after build, before deploy).
- [x] **Phase 10 — `CSRF_TRUSTED_ORIGINS` added**: Missing from production settings — required for all HTMX POST requests to succeed on Railway domain. Added to both settings dict and env vars section.
- [x] **Phase 6 — upfront bracket prediction clarified**: Overview now explicitly states this is an upfront bracket-prediction system (all 103 matches predicted before locking, knockout matchups derived from user's own predicted standings — not official results).
- [x] **Phase 1 — `AppConfig.name` setup added**: New `Changes item 8` documents the `apps/` subdirectory AppConfig requirement for all apps.
- [x] **Phase 1 — `CELERY_TASK_ALWAYS_EAGER` added to local settings**: New `Changes item 9` documents this setting to prevent Celery broker dependency during testing in Phases 2–7.
- [x] **Phase 1 — `check --deploy` settings fixed**: Automated Verification now specifies production settings for `--deploy` check to avoid false positives from `DEBUG=True`.
- [x] **Phase 4 — integration helper test added**: New `Changes item 4` documents a `@pytest.mark.django_db` test for `get_predicted_group_standings()`.
- [x] **Phase 8 — Celery 5 test approach updated**: Test note updated to clarify `CELERY_TASK_ALWAYS_EAGER` (set in Phase 1) and direct `.apply()` as alternatives.
- [x] **Phase 9 — tie-handling specified**: Leaderboard uses dense ranking; tied users shown at same rank, secondary sort by nickname.
- [x] **Phase 10 — `STATICFILES_STORAGE` replaced with `STORAGES`**: Updated to Django 5.1+ compatible API.
