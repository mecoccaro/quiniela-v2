---
date: 2026-05-08T00:00:00-03:00
researcher: miguel
git_commit: 707c02168ec37f107c4523bdb9e7feac688f2d76
branch: master
repository: quiniela-v2
topic: "Football prediction pool portal — architecture, tech stack, and domain model"
tags: [research, architecture, domain-model, tech-stack, world-cup-2026, quiniela]
status: complete
autonomy: critical
last_updated: 2026-05-08
last_updated_by: miguel
---

# Research: Football Prediction Pool Portal — Architecture, Tech Stack & Domain Model

**Date**: 2026-05-08  
**Researcher**: miguel  
**Git Commit**: `707c021`  
**Branch**: master

---

## Research Question

Design the architecture, recommend the technology stack, define the domain model, and assess feasibility for a football prediction pool portal (`quiniela-v2`). Primary focus: 2026 FIFA World Cup. Must support any football competition. Simplest possible architecture that is easy to maintain and to work on collaboratively with Claude Code.

---

## Summary

The project is a prediction pool portal where users predict match results for football tournaments and compete on a leaderboard. The recommended stack is **Django + PostgreSQL + Celery + Redis**, deployed as a **monolith on Railway.app**, with **Django templates + HTMX + Tailwind CSS** for the frontend. This approach minimizes operational complexity, leverages Django's built-in admin (which directly satisfies the admin panel requirements), and stays entirely in Python — consistent with the repository's `.gitignore` footprint.

The domain is straightforward: tournaments contain matches, pools group users around a tournament, users submit predictions, and an async worker recalculates scores when official results are entered. The most complex piece is the FIFA group-stage tiebreaker algorithm, which involves head-to-head comparisons among tied teams across up to 4 levels of criteria.

The entire application is buildable by two people (human + Claude Code) in 6–10 weeks to a working MVP.

---

## Detailed Findings

### 1. FIFA 2026 World Cup Format (Tournament Domain)

**Group stage:**
- 48 teams in 12 groups (A–L), 4 teams per group
- Each team plays 3 matches (round-robin within the group)
- Total group stage matches: 12 groups × 6 matches = **72 matches**

**Qualification from groups:**
- Top 2 teams from each group advance → 24 teams
- Best 8 third-place finishers (out of 12) advance → 8 teams
- Total advancing: **32 teams** (introduces a new "Round of 32")

**Knockout stage rounds:**
1. Round of 32 (16 matches)
2. Round of 16 (8 matches)
3. Quarterfinals (4 matches)
4. Semifinals (2 matches)
5. Third-place match (1 match)
6. Final (1 match)

Total tournament matches: 72 + 31 = **103 matches**

**Group stage tiebreaker criteria (in order):**

When two or more teams are level on points after the group stage:

*First, apply head-to-head criteria among the tied teams:*
1. Points in head-to-head matches between tied teams
2. Goal difference in head-to-head matches between tied teams
3. Goals scored in head-to-head matches between tied teams

*If still tied (only among teams that remain tied after step above):*
4. Same head-to-head criteria applied again to the remaining tied subset

*If still tied, apply overall group criteria:*
5. Goal difference across all group matches
6. Goals scored across all group matches
7. Fair play score (conduct):
   - Yellow card: −1 pt
   - Two yellows (indirect red): −3 pts
   - Direct red: −4 pts
   - Yellow + red: −5 pts
8. FIFA World Ranking (latest)

**Ranking the 8 best third-place teams (cross-group comparison):**
1. Points
2. Goal difference
3. Goals scored
4. Fair play score
5. FIFA World Ranking

**Design implication:** The tiebreaker algorithm must be implemented as a deterministic function that takes a list of group matches with results and returns the final group standing. It must handle the recursive head-to-head subset logic correctly.

---

### 2. Technology Stack Recommendation

#### Backend: Django 5.x

**Why Django over FastAPI/Flask:**
- Built-in admin interface covers ~80% of the admin panel requirements out of the box (viewing participants, pool assignments, entering official results)
- Built-in authentication (registration, login, password management)
- ORM with migrations for PostgreSQL
- Django REST Framework available if an API layer is needed later
- Battle-tested for CRUD-heavy, tournament-style applications
- Extensive ecosystem (django-allauth for social login, django-celery-beat for scheduled tasks)

#### Frontend: Django Templates + HTMX + Tailwind CSS

**Why not a separate SPA (React/Vue/Next.js):**
- A separate frontend doubles the codebase surface area and introduces a build pipeline, separate deployment, and API contract maintenance
- HTMX enables dynamic interactions (live leaderboard updates, inline form submission, prediction confirmation modals) without a JavaScript framework
- Django templates render server-side — simpler mental model, easier for Claude Code to reason about the full stack in one place
- Tailwind CSS via CDN (or PostCSS in dev) for styling without a design system overhead

**What HTMX handles well for this app:**
- Prediction form submission per match (swap result, show confirmation)
- Leaderboard polling / auto-refresh
- Admin result entry with instant feedback
- Modal for champion + top scorer confirmation

#### Database: PostgreSQL

- Natural fit for relational tournament data (groups, matches, standings, predictions, scores)
- Django ORM maps cleanly to the domain model
- Complex leaderboard queries (rank, points aggregation) benefit from PostgreSQL's window functions
- Use SQLite for local development only

#### Async task queue: Celery + Redis

**What it handles:**
- After an admin enters an official match result, a Celery task fans out to recalculate points for every prediction across all active pools
- This avoids blocking the admin's HTTP request and keeps UI responsive

**Simpler alternative if Celery feels heavy:** Django Q2 (single process, uses PostgreSQL as the broker — no Redis needed). Good for MVP, can upgrade to Celery later.

#### Hosting: Railway.app

**Why Railway:**
- One-click PostgreSQL, Redis, and web service in the same project
- Git push to deploy (GitHub integration)
- Environment variables via dashboard
- Free tier for MVP; scales to ~$10–20/month for production
- Native support for Celery workers as a second service in the same project
- No infrastructure configuration needed (vs. EC2, GCP, etc.)

**Alternative:** Render.com — nearly identical offering, slightly different UX. Either works.

#### Summary table

| Layer | Choice | Rationale |
|---|---|---|
| Backend language | Python 3.12+ | Established by repo `.gitignore` |
| Web framework | Django 5.x | Built-in admin, auth, ORM, migrations |
| Frontend | Django templates + HTMX + Tailwind | Monolith, no build step, full-stack Python |
| Database | PostgreSQL (prod) / SQLite (dev) | Relational, complex queries |
| Async tasks | Celery + Redis (or Django Q2 for MVP) | Async score recalculation |
| Hosting | Railway.app | Simplest multi-service deployment |
| Package manager | `uv` | Fastest, modern Python tooling |
| Linting | Ruff | Already in `.gitignore`, covers format + lint |
| Type checking | mypy | Already in `.gitignore` |
| Testing | pytest + pytest-django | Standard Django testing |

---

### 3. Domain Model

#### Core Entities

```
Tournament
  - id, name (str), slug (str)
  - competition_type (world_cup | league | cup)
  - status (upcoming | group_stage | knockout | completed)
  - num_groups (int), teams_per_group (int)
  - third_place_advancers (int)  # 8 for WC2026
  - scoring_config (JSON)        # exact_score_pts, correct_result_pts, etc.

Team
  - id, name (str), fifa_code (str, 3-letter), flag_url (str)

TournamentTeam
  - tournament FK, team FK
  - group (CharField: "A"–"L")
  - fifa_ranking (int)  # for tiebreaker of last resort

Match
  - id, tournament FK
  - stage (group | r32 | r16 | qf | sf | third_place | final)
  - group (nullable, e.g. "A")
  - home_team FK, away_team FK
  - scheduled_at (datetime)
  - home_score (nullable int)   # official result
  - away_score (nullable int)   # official result
  - status (scheduled | live | completed)

Pool
  - id, name (str), tournament FK
  - status (open | locked | completed)
  - lock_deadline (datetime, nullable)

PoolMembership
  - pool FK, user FK
  - joined_at (datetime)
  - predictions_submitted (bool)  # True = locked, cannot modify

User  (extends AbstractUser)
  - first_name, last_name, nickname (unique), email, password
  - is_admin (bool)  # or use Django groups

Prediction
  - user FK, pool FK, match FK  [unique together]
  - predicted_home_score (int)
  - predicted_away_score (int)
  - points_awarded (nullable int)  # set after official result

PoolChampionPick
  - user FK, pool FK  [unique together]
  - team FK
  - points_awarded (nullable int)

PoolTopScorerPick
  - user FK, pool FK  [unique together]
  - player_name (str)  # or FK to Player table
  - points_awarded (nullable int)

Player  (optional, for structured top scorer)
  - id, name (str), team FK

MatchConduct  (for tiebreaker fair play score — one row per team per match)
  - match FK, team FK
  - yellow_cards (int), indirect_red_cards (int)
  - direct_red_cards (int), yellow_then_red_cards (int)
  - fair_play_score (int, computed: yellow×−1 + indirect_red×−3 + direct_red×−4 + yellow_red×−5)

LeaderboardEntry  (denormalized, recalculated async)
  - pool FK, user FK  [unique together]
  - total_points (int)
  - rank (int)
  - last_calculated_at (datetime)
```

#### Key Relationships

```
Tournament ──< Match            (one tournament, many matches)
Tournament ──< TournamentTeam  (teams assigned to groups)
Tournament ──< Pool             (a tournament can have many pools)
Pool ──< PoolMembership ──> User
Pool ──< Prediction ──> Match
Pool ──< PoolChampionPick ──> Team
Pool ──< PoolTopScorerPick
Pool ──< LeaderboardEntry ──> User
```

#### Business Rules

1. **Prediction locking:** A user's predictions for a pool are locked when `PoolMembership.predictions_submitted = True`. This is set by the user explicitly confirming their champion + top scorer pick (final submission action). Once locked, the user cannot modify any prediction in that pool.

2. **Match-level locking:** Even before a user submits, individual match predictions should be locked once the match `status = live` or `completed` (to prevent editing after kickoff).

3. **Pool-level locking:** The admin can lock the entire pool (`Pool.status = locked`) which prevents any further prediction entry.

4. **Score recalculation:** Triggered asynchronously when an admin sets an official result on a Match. The Celery task iterates over all Prediction rows for that match across all pools and calculates `points_awarded`. Then recalculates `LeaderboardEntry` for each affected pool.

5. **Knockout bracket derivation:** For knockout round predictions, the user must first complete group stage predictions. The system simulates the group standings from the user's predictions (applying FIFA tiebreaker rules) to determine which teams the user predicted to advance — those become the available teams for Round of 32 prediction slots.

6. **Third-place team selection:** After the user predicts all group matches, the system must apply the 8-best-third-place algorithm across all 12 groups to determine which third-place teams the user predicts will advance.

7. **Scoring config per pool:** Points per exact score, correct result, champion pick, and top scorer pick are stored as JSON on the Tournament (or Pool) and applied at calculation time.

---

### 4. Technical Challenges

#### A. Group Standings Calculation (Predicted)

This is the most algorithmically complex part. Must implement:
1. Collect all 6 group match predictions for a user
2. Build a standings table (points, GD, GF, GA) for each of the 4 teams
3. Sort by points descending
4. For ties: apply head-to-head subset criteria recursively
5. Handle 3-way and 4-way ties

**Approach:** A pure Python function `calculate_group_standings(matches: list[MatchResult]) -> list[TeamStanding]` that is unit-testable independently of Django. This function is shared for both user-predicted standings and official standings.

**Complexity:** Medium-high. The recursive head-to-head logic needs careful implementation and thorough test coverage with edge cases (3-way tie where H2H resolves two but not the third, etc.).

#### B. Third-Place Cross-Group Ranking

After calculating predicted standings for all 12 groups, collect the 12 third-place teams and rank them by the cross-group criteria (points, GD, GF, conduct, FIFA ranking). The 8 best advance.

**Approach:** Straightforward sort after group standings are calculated. Medium complexity.

#### C. Knockout Bracket Progression

The Round of 32 bracket must be built from the predicted group outcomes. FIFA defines which group winners face which third-place finishers (the bracket structure is predetermined).

**Important complexity — third-place slot assignment:** FIFA uses a pre-defined lookup table that maps the specific combination of groups that produced the 8 advancing third-place teams to concrete R32 match slots. For example: "if the third-place teams came from groups A, B, C, D, then the best one plays against the winner of group X." This means the R32 bracket for third-place teams is **dynamically determined** based on which 8 of the 12 groups produced the advancing third-place finishers — it is not a static bracket config. The bracket configuration must encode this lookup table (12-choose-8 = 495 possible combinations, but FIFA has pre-specified all of them).

**Approach:** Store the FIFA-defined bracket lookup table as a fixture/config (JSON or database table). After predicting which 8 third-place teams advance, look up the correct R32 slot assignment from this table.

#### D. Async Score Recalculation

When an admin enters an official result:
1. Admin POSTs result → Django saves official score on Match
2. Django triggers Celery task: `recalculate_pool_scores.delay(match_id)`
3. Celery worker fetches all Predictions for that match_id
4. For each prediction: compare predicted vs. official → award points
5. After all match predictions updated: re-aggregate LeaderboardEntry per pool

**Approach:** Celery task with `transaction.atomic()` for each pool's leaderboard update. Signal (`post_save` on Match) can trigger the task automatically.

#### F. Knockout Round Scoring (Extra Time & Penalties)

Knockout matches cannot end in a draw — if level after 90 minutes, they go to extra time and then a penalty shootout. The Prediction model as defined only captures predicted home/away scores. For knockout rounds, the scoring system must decide:

- Do users predict the 90-minute scoreline only? (Simpler: if the match ends level and goes to ET/pens, any predicted draw scores as "correct result" only.)
- Or do users also predict the ET/penalties winner? (Adds a `predicted_winner FK(Team)` field to Prediction for knockout rounds.)

This affects both the Prediction model and the `scoring_config` schema. This question must be resolved before implementing the scoring engine.

**Approach (recommended default):** Predict 90-minute scoreline only. If the official 90-minute result is a draw in a knockout match, evaluate predictions against the 90-minute score. Award points for correct result (draw) if predicted correctly. The ultimate winner (via ET/pens) is reflected in subsequent round match assignments but is not separately predicted.

#### G. Prediction Submission Flow

The user must predict all group stage matches before unlocking knockout predictions. This gate must be enforced server-side (not just UI).

**Approach:** A `PoolMembership.group_stage_complete` flag (or computed property) that checks if all 72 group stage matches have a prediction. The view for knockout predictions validates this before rendering.

**Edge case:** Users predict all group matches upfront (before the tournament starts). Knockout matches are not pre-created in the database — they are created by the admin as teams advance. Users predict knockout matches one round at a time as they become available. The submission lock (`predictions_submitted`) is therefore not an all-at-once event — it applies when the user explicitly confirms champion + top scorer picks. After that, remaining round predictions are blocked. This differs from a "predict the whole tournament bracket in one go" model.

---

### 5. Feasibility Assessment

| Feature | Complexity | Notes |
|---|---|---|
| User registration/auth | Low | Django built-in |
| Admin panel (view, assign) | Low | Django admin out of the box |
| Pool CRUD | Low | Standard Django models/views |
| Group stage prediction entry | Medium | Form per match, 72 matches per user |
| Group standings calculation | High | Tiebreaker algorithm, unit-test heavily |
| Third-place cross-group ranking | Medium | Sort after standings |
| Knockout bracket prediction | Medium | Bracket config + UI |
| Champion + top scorer pick | Low | Simple form |
| Prediction locking | Low | Flag check in view + serializer |
| Admin result entry | Low | Django admin or simple form |
| Async score recalculation | Medium | Celery task, straightforward logic |
| Leaderboard | Low-Medium | Aggregate query + ranking |
| Multi-pool support | Low | Already in data model |
| Cover any competition | Medium | Generic enough if scoring_config is flexible |
| Data seeding (teams, matches) | Low-Medium | Management command or fixture import; public football APIs available |
| Third-place bracket slot lookup table | Medium | FIFA publishes the full 495-combination table; must be encoded as a fixture |
| Knockout ET/penalties handling | Low | Decision needed (Open Q11); recommended: 90-min scoreline only |

**Overall assessment:** MVP (group stage predictions + leaderboard + admin result entry) is achievable in 4–6 weeks of focused work. Full tournament coverage through the final is 6–10 weeks. The group standings tiebreaker is the one area that requires careful engineering and test coverage.

---

## Code References

_Not applicable — this is a greenfield project with no existing source files. File:line references will be added once implementation begins._

---

## Open Questions

1. **Scoring rules:** What are the exact point values for correct result vs. exact score vs. champion pick vs. top scorer? Should these be configurable per pool?
2. **Top scorer:** Is the top scorer pick a free-text player name or a selection from a list of players seeded into the system?
3. **Yellow/red card tracking for tiebreakers:** Will the admin enter conduct data per match, or is the FIFA ranking the final tiebreaker in practice?
4. **Match-level prediction lock:** Should individual predictions lock at match kickoff, or only at user submission? (Match kickoff lock is more fair but requires knowing match times.)
5. **Social/auth:** Email/password only, or social login (Google)?
6. **Notifications:** Email notifications when official results are entered? When a pool is locked?
7. **Pool invitation flow:** How does a user join a pool? Admin assigns directly, or is there an invite link/code?
8. **Multiple languages:** Spanish UI? (Given "quiniela" is a Spanish term)
9. **Data seeding:** Who loads the 48 WC2026 teams, group assignments, and 72 scheduled group matches into the database? Via Django admin manually, a management command + fixture, or an import from a public football API (e.g., football-data.org, API-Football)?
10. **Default scoring schema for `scoring_config`:** Proposed default: `{"exact_score": 3, "correct_result": 1, "champion": 5, "top_scorer": 3}`. Should this be configurable per pool or per tournament only?
11. **Knockout round prediction:** Predict 90-minute scoreline only (recommended), or also predict ET/penalties winner? Affects Prediction model and scoring engine design.
12. **Generalization to other competitions:** The tiebreaker algorithm is FIFA World Cup-specific. Applying to Champions League, Copa América, or league formats requires different group advancement rules. Decide: is this app World Cup-focused only, or truly generic? If generic, tiebreaker logic must be pluggable (strategy pattern per competition type).

---

## Appendix

### Architecture Diagram (Conceptual)

```
Browser
  │
  ├─ Django Views (server-rendered HTML + HTMX partials)
  │    ├─ User auth views
  │    ├─ Pool prediction views
  │    ├─ Leaderboard view
  │    └─ Admin views (Django admin + custom)
  │
  ├─ Django ORM → PostgreSQL
  │
  └─ Celery Worker (async)
       └─ Score recalculation task
            └─ Triggered by: Match result saved (post_save signal)

Hosting: Railway.app
  ├─ Web service (Django + gunicorn)
  ├─ Worker service (Celery)
  ├─ PostgreSQL (managed)
  └─ Redis (managed, Celery broker)
```

### Suggested Project Layout

```
quiniela-v2/
├── manage.py
├── pyproject.toml
├── quiniela/              # Django project config
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── celery.py
├── apps/
│   ├── users/             # Custom user model, auth
│   ├── tournaments/       # Tournament, Team, Match, Group models
│   ├── pools/             # Pool, PoolMembership, Prediction models
│   ├── predictions/       # Prediction entry views, standings calc
│   ├── leaderboard/       # LeaderboardEntry, scoring logic
│   └── admin_panel/       # Custom admin views (beyond Django admin)
├── templates/
├── static/
└── tests/
```

### Sources

- [2026 FIFA World Cup: Format, groups, full match schedule — ESPN](https://www.espn.com/soccer/story/_/id/47108758/2026-fifa-world-cup-format-tiebreakers-fixtures-schedule)
- [Every World Cup 2026 group stage tiebreaker — FourFourTwo](https://www.fourfourtwo.com/competition/every-world-cup-2026-group-stage-tiebreaker-what-happens-if-teams-finish-with-the-same-points)
- [World Cup 2026 format explained — FourFourTwo](https://www.fourfourtwo.com/features/world-cup-2026-format-explained-tournament-draw-group-stage-tiebreakers-and-knockout-routes)
- [2026 World Cup Third-Placed Teams Qualification Rules](https://worldcuplocaltime.com/2026-world-cup-third-place-qualification/)
- [Official FIFA: Groups, how teams qualify, tie-breakers](https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/groups-how-teams-qualify-tie-breakers)

---

## Review Errata

_Reviewed: 2026-05-08 by Claude Code_

### Applied

- [x] **Domain model gap — conduct data entity:** Added `MatchConduct` entity to Domain Model to represent per-team, per-match card tracking needed for fair play tiebreaker and third-place ranking criteria.
- [x] **Knockout round scoring underspecified:** Added Technical Challenge F covering extra time / penalty shootout handling, with a recommended default approach (90-minute scoreline only).
- [x] **Third-place bracket slot assignment complexity understated:** Expanded Technical Challenge C to explicitly note the FIFA pre-defined lookup table (495 combinations) and that slot assignment is dynamic based on which groups produced the advancing third-place teams.
- [x] **`scoring_config` JSON schema undefined:** Added Open Question 10 with a proposed default scoring schema.
- [x] **Data seeding / tournament initialization unaddressed:** Added Open Question 9 (data loading options) and a row in the Feasibility table.
- [x] **Knockout prediction submission edge case:** Clarified in Technical Challenge G that knockout matches are created round-by-round and users predict them progressively, not in a single all-at-once bracket pick.
- [x] **Competition generalization underspecified:** Added Open Question 12 asking whether the tiebreaker should be pluggable (strategy pattern) for non-World-Cup competitions.
- [x] **Code References table missing:** Added section marked N/A for greenfield, per template requirement.
- [x] **"Cover any competition" feasibility rating:** Added clarifying note in Feasibility table that tiebreaker is WC-specific; generalization requires pluggable logic.
