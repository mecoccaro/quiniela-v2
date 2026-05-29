---
date: 2026-05-28T00:00:00-04:00
researcher: miguel
git_commit: 7d848c4
branch: master
repository: quiniela-v2
topic: "Feature batch: flags, knockout carousel, neutral Spanish, pool monitoring view, per-phase scoring, bracket-position bonus, third-place conduct tiebreaker, top scorer player list, password recovery, branding rename to La Gansa"
tags: [research, codebase, flags, knockout, i18n, leaderboard, scoring, auth, branding, predictions, standings]
status: complete
autonomy: critical
last_updated: 2026-05-28
last_updated_by: miguel
---

# Research: Feature Batch — La Gansa v2

**Date**: 2026-05-28  
**Researcher**: miguel  
**Git Commit**: 7d848c4  
**Branch**: master

## Research Question

Research the current codebase state to support implementing:
1. Country flags in team displays (predictions + picks views)
2. Knockout view by phase/round with carousel-style switcher
3. Language: switch from Argentine voseo to neutral Latin American Spanish
4. New pool monitoring view: games per date with all participants' picks and points
5. Per-phase/round scoring configuration (already partially exists)
6. Bracket-position bonus scoring (new concept)
7. Third-place conduct tiebreaker manual pick UI
8. Top scorer picker: close free-text, add searchable player list from WC2026 squads
9. Password recovery module (email + nickname match)
10. Branding: rename "Quiniela 2026" → "La Gansa", add logo image

---

## Summary

The codebase is a monolith Django 5.x app with HTMX for partial updates. The `Team` model already has a `flag_url` field but it is never populated (always `""`). No template renders flags. Knockout stages are all shown in one partial — no phase-switching UI exists. The UI is written in Argentine-flavored Spanish (voseo: "tenés", "ingresás") hardcoded in templates and forms. A new "pool monitoring" view does not exist; while `Match.scheduled_at` is a nullable DateTimeField it is never populated by the data loader. Per-stage scoring config is already implemented and configurable via JSON on both `Tournament` and `Pool`, but bracket-position bonuses are not. Third-place tiebreaking ends at FIFA ranking — no conduct score field or manual pick UI exists. The top scorer is a free-text CharField with no player model. No password reset is wired up and no email backend is configured. "Quiniela 2026" is hardcoded in 5 template locations; the nav logo is a text+emoji only — no image.

---

## Detailed Findings

### 1. Country Flags

**Team model** (`apps/tournaments/models.py:23-26`):
```python
class Team(models.Model):
    name = models.CharField(max_length=100)
    fifa_code = models.CharField(max_length=3, unique=True)
    flag_url = models.URLField(blank=True)
```
The `flag_url` field exists as a `URLField(blank=True)`. It is never populated.

**JSON data** (`data/wc2026.json`): Each team entry has only `name`, `fifa_code`, `fifa_ranking`. No `flag_url` key. The loader (`apps/tournaments/management/commands/load_wc2026.py:54`) uses `t.get("flag_url", "")`, so all teams load with empty `flag_url`.

**Templates**: None of the following templates reference `flag_url` or any flag image:
- `templates/predictions/group_stage.html` — shows `match.home_team.name` / `match.away_team.name` (lines 56, 70)
- `templates/predictions/partials/knockout_stages.html` — shows `slot.home_team.name|default:"TBD"` / `slot.away_team.name|default:"TBD"` (lines 13-15, 68-70); uses `slot.home_team.fifa_code` / `slot.away_team.fifa_code` only in draw tiebreaker dropdown
- `templates/predictions/partials/group_standings.html` — shows `team.name` (line 25)
- `templates/predictions/picks.html` — shows `predicted_champion.name` (line 27)
- `templates/leaderboard/my_predictions.html` — shows team names in text

**Strategy for flags**: The `fifa_code` field (3-letter, e.g. `"ARG"`, `"FRA"`, `"MEX"`) maps directly to standard emoji flags and to Flagpedia/similar CDN URLs (e.g. `https://flagcdn.com/w40/ar.svg`). The FIFA 3-letter code can be mapped to ISO 3166-1 alpha-2 for flag CDN lookups, or emoji flags can be rendered via a template filter. Alternatively, `flag_url` in `wc2026.json` can be populated with Flagpedia URLs and re-loaded.

---

### 2. Knockout View by Phase (Carousel)

**Current state**: The `KnockoutPredictionsView` (`apps/predictions/views.py:131-164`) builds a `stages` list ordered `r32 → r16 → qf → sf → final` with labels from `STAGE_LABELS` dict. All stages are passed together to a single partial.

The template `templates/predictions/knockout.html` includes the entire `predictions/partials/knockout_stages.html` inside a single `<div id="ko-bracket">` (line 28). The partial iterates all stages sequentially, each wrapped in a collapsible `<details>` element (partial line 2).

**HTMX pattern**: On any knockout prediction save, `SaveKnockoutPredictionView` (`views.py:167-206`) rebuilds the entire bracket and returns the full `knockout_stages.html` partial. The `hx-target="#ko-bracket"` + `hx-swap="innerHTML"` pattern (partial lines 22-23) replaces the entire bracket div.

**State preservation**: An IIFE in `knockout.html` (lines 40-95) snapshots and restores open/closed `<details>` state and scroll position around HTMX swaps.

**What's missing for a carousel**: No phase-tab UI, no active-phase state, no per-phase filtering. The partial renders all rounds in one pass; there is no per-round partial. A round switcher would need either: (a) server-side filtering via a query param or URL segment, or (b) client-side CSS show/hide of stage sections.

---

### 3. Language: Argentine Voseo → Neutral Latin American Spanish

**Current language config**: `LANGUAGE_CODE = "es"` (`quiniela/settings/base.py:71`), `USE_I18N = True`. No `.po`/`.mo` translation files exist; all strings are hardcoded directly in templates and Python forms.

**Argentine voseo instances found**:

In templates:
- `templates/users/login.html:33` — `"¿No tenés cuenta?"` → *tenés* (voseo)
- `templates/users/register.html:35` — `"¿Ya tenés cuenta?"` → *tenés* (voseo)
- `templates/partials/nav.html:6` — `"¿Cómo jugar?"` (neutral ✓)
- `templates/users/dashboard.html:47` — `"Todavía no estás en ninguna quiniela."` → *estás* (acceptable)
- `templates/users/dashboard.html:48` — `"Pedile al administrador"` → *pedile* (voseo)
- `templates/partials/howto_modal.html` (not read, likely has voseo)
- `templates/partials/faq_modal.html` (not read, likely has voseo)

In Python forms:
- `apps/predictions/forms.py:28` — `"Tenés que elegir un ganador cuando el resultado es empate."` → *tenés* (voseo)
- `apps/users/forms.py:24` — `"Las contraseñas no coinciden."` (neutral ✓)

In templates (group standings partial):
- `templates/predictions/partials/group_standings.html` — `"Ingresá resultados para ver la tabla."` → *ingresá* (voseo)

**Full extent**: The howto/faq modals and submission confirmation template also likely contain Argentine forms but were not fully read. A grep for voseo markers (`tenés`, `ingresá`, `pedile`, `elegí`, `hacé`, `poné`) is recommended to find all instances.

---

### 4. Pool Monitoring View (Games by Date)

**No such view exists**. The three leaderboard views are: `LeaderboardView` (all-time totals), `MyPredictionsView` (current user's picks across all stages), `ParticipantsView` (all participants' champion/scorer picks + total points). None filter by date.

**`Match.scheduled_at`** (`apps/tournaments/models.py:66`): `DateTimeField(null=True, blank=True)`. Field exists but is **never populated** — the `load_wc2026.py` command does not pass `scheduled_at` to `Match.objects.get_or_create`.

**JSON data**: `data/wc2026.json` contains no match schedule. Group matches are generated via `itertools.combinations` (round-robin) without dates. Knockout matches are loaded from `data/knockout_bracket.json` as placeholders also without dates.

**What needs to be added for this view**:
- Match dates in the JSON data or a separate schedule file
- The loader must populate `Match.scheduled_at`
- A new view: queries matches for a given date, for each match queries `Prediction` records from all `PoolMembership` users, cross-references `points_awarded`, and renders per-user picks + points
- A date-switcher UI (HTMX query param update or link-based navigation)

**Existing patterns that can be reused**:
- `ParticipantsView` (`leaderboard/views.py:113-148`) already builds a per-user data structure with champion/scorer picks and can be adapted
- The leaderboard table partial (`leaderboard/partials/leaderboard_table.html`) uses HTMX polling that can be adapted for date switching

---

### 5. Per-Phase/Round Scoring Configuration

**Already implemented**. The scoring system supports per-stage configuration via `DEFAULT_SCORING_CONFIG` (`apps/leaderboard/scoring.py:11-21`):

```python
DEFAULT_SCORING_CONFIG = {
    "group":       {"exact_score": 3, "correct_result": 1},
    "r32":         {"exact_score": 4, "correct_result": 2, "pens_winner": 1},
    "r16":         {"exact_score": 5, "correct_result": 2, "pens_winner": 1},
    "qf":          {"exact_score": 6, "correct_result": 3, "pens_winner": 1},
    "sf":          {"exact_score": 7, "correct_result": 3, "pens_winner": 1},
    "third_place": {"exact_score": 5, "correct_result": 2, "pens_winner": 1},
    "final":       {"exact_score": 10, "correct_result": 4, "pens_winner": 2},
    "champion":    5,
    "top_scorer":  3,
}
```

**Fallback chain** (`scoring.py:24-30`): `pool.scoring_config` → `pool.tournament.scoring_config` → `DEFAULT_SCORING_CONFIG`. Both `Pool.scoring_config` and `Tournament.scoring_config` are `JSONField`.

**Score lookup** (`scoring.py:41-58`): `_stage_values(stage, config)` handles both new per-stage format and a legacy flat format for backwards compatibility.

**Scoring function** (`scoring.py:61-88`): `score_prediction(stage, predicted_home, predicted_away, home_score, away_score, predicted_winner_id, official_knockout_winner_id, config)`.

**What's NOT implemented**: There is no `bracket_position` or `team_in_correct_slot` bonus in the scoring config or function.

---

### 6. Bracket-Position Bonus Scoring

**Not implemented**. The scoring function (`scoring.py:61-88`) only scores: exact scoreline, correct result (outcome), and penalty winner. There is no concept of "team reached the correct bracket slot" (e.g., Germany predicted to reach the semifinal and indeed reached it).

**What would be needed**: A new scoring dimension tracking predicted vs. actual team in each knockout slot, separate from match score predictions. This would require:
- A way to store "predicted team for slot X" — currently implicit via the bracket (if Germany beats Brazil in QF predicted, Germany is "in" the SF slot for that side of the bracket)
- A new config key, e.g. `"correct_slot": 2`, per stage
- A new scoring path in `recalculate_pool_scores` or a separate task that fires when knockout matches complete

**Existing mechanism that could be extended**: `build_predicted_knockout_bracket` in `services.py` already derives which teams the user predicts to reach each bracket slot. The actual bracket (from official results) is similarly derivable. Comparing predicted slot occupants vs. actual slot occupants per stage is the core computation.

---

### 7. Third-Place Conduct Tiebreaker

**Current state**: `standings.py` implements the FIFA tiebreaker chain ending at FIFA ranking:
- `_overall_sort` (`standings.py:73-85`): sorts by overall GD → GF → FIFA ranking ascending
- `rank_third_place_teams` (`standings.py:176-189`): sorts all third-placed teams by points → GD → GF → FIFA ranking

**No conduct score**:
- `TeamStanding` dataclass (`standings.py:12-23`): no `conduct_score` field
- `TournamentTeam` model (`tournaments/models.py:32-42`): no `conduct_score` field
- No form, view, or admin panel for entering conduct scores

**Bracket impact**: In `services.py`, `rank_third_place_teams` is called and the top 8 are assigned `third_ids[0]` through `third_ids[7]`. These map to `3RD_1` through `3RD_8` in `knockout_bracket.json`. The assignment is purely rank-by-index; the real FIFA table mapping specific group combinations to specific R32 slots is noted as "to be implemented" in `data/r32_bracket.json` but not connected to the active bracket logic.

**What's needed for conduct tiebreaker UI**: A new Django model field or temporary UI for admin to enter conduct scores when the tiebreaker reaches that level; plus a corresponding `TeamStanding.conduct_score` field and sort step.

---

### 8. Top Scorer Player List

**Current state**:
- Model: `PoolTopScorerPick.player_name = CharField(max_length=100)` (`pools/models.py:74`) — free text
- Form: `TopScorerPickForm.player_name = CharField(max_length=100)` (`predictions/forms.py:38-39`) — free text, no validation
- Template: `templates/predictions/picks.html:43-50` — `<input type="text" name="player_name">` with HTMX auto-save on change

**No player model, no player table, no dropdown, no autocomplete**.

**Player data source**: https://as.com/futbol/mundial/listas-de-convocados-para-el-mundial-2026-selecciones-y-todos-los-jugadores-que-estaran-en-la-copa-del-mundo-f202605-n-5/ — 48-team WC2026 squad lists (not yet scraped/stored).

**Implementation path**: Either (a) store players as a JSON fixture or new `Player` model with FK to `Team`, or (b) store a static JSON list of player names. The pick model can remain `CharField` for the stored name; the UI becomes a `<select>` or searchable autocomplete (e.g. using `<datalist>` or a JS library) populated from the player list.

---

### 9. Password Recovery

**No password reset exists**. `apps/users/urls.py` has only 4 routes: register, login, logout, dashboard.

**User model** (`apps/users/models.py`):
- `USERNAME_FIELD = "email"` (line 30)
- `email = models.EmailField(unique=True)` (line 28)
- `nickname = models.CharField(max_length=50, unique=True)` (line 27)
- Both email and nickname are unique — can serve as combined identity proof

**Email backend**: No `EMAIL_BACKEND` in settings. Django default (`smtp`) applies but no SMTP credentials configured. For a simple "no email" approach, the recovery could match email+nickname and immediately show a password reset form (no token email flow).

**Django built-ins available**:
- `django.contrib.auth.views.PasswordResetView` — sends token via email (requires email backend)
- `django.contrib.auth.views.SetPasswordView` — renders new password form

**Alternative simple approach** (as requested): Match `email` + `nickname` → if both match a user, show `SetPasswordView`-style form directly in the request (no email token, no email backend needed). This is simpler but less secure (guessable if attacker knows both).

**What needs to be created**:
- `PasswordRecoveryView` — GET renders email+nickname form; POST validates both match a user, stores user PK in session, redirects to set-password step
- `SetPasswordView` — GET/POST renders new password form; checks session for user PK; calls `user.set_password()`; clears session; logs in; redirects to dashboard
- 2 new templates
- 2 new URLs in `apps/users/urls.py`
- "Forgot password?" link added to `templates/users/login.html`

---

### 10. Branding: "Quiniela 2026" → "La Gansa" + Logo Image

**"Quiniela 2026" occurrences**:

| File | Line | Context |
|---|---|---|
| `templates/base.html` | 6 | Default `<title>` block: `{% block title %}Quiniela 2026{% endblock %}` |
| `templates/partials/nav.html` | 3 | Nav logo link: `⚽ Quiniela 2026` |
| `templates/users/login.html` | 3 | `{% block title %}Ingresar — Quiniela 2026{% endblock %}` |
| `templates/users/register.html` | 3 | `{% block title %}Registrarse — Quiniela 2026{% endblock %}` |
| `templates/users/dashboard.html` | 3 | `{% block title %}Panel — Quiniela 2026{% endblock %}` |

Additional pages (`knockout.html`, `group_stage.html`, `picks.html`, `my_predictions.html`, `participants.html`, `leaderboard.html`) likely also override `{% block title %}` with "Quiniela 2026" — not confirmed.

**Nav logo** (`templates/partials/nav.html:3`): `<a href="{% url 'dashboard' %}" class="font-bold text-lg tracking-wide">⚽ Quiniela 2026</a>` — text + emoji, no `<img>`.

**Static files setup**: `STATIC_URL = "/static/"`, `STATIC_ROOT = BASE_DIR / "staticfiles"`. No `STATICFILES_DIRS` configured in base.py. Whitenoise middleware is active. No `static/` directory was found in the project root.

**What's needed for the logo**:
- Add `STATICFILES_DIRS = [BASE_DIR / "static"]` to settings if not present
- Create `static/images/` directory and place the logo image there
- Update `nav.html` to replace the emoji text with `{% load static %}<img src="{% static 'images/logo.png' %}" ...>`
- Replace all 5+ "Quiniela 2026" occurrences with "La Gansa"

---

## Code References

| File | Line | Description |
|------|------|-------------|
| `apps/tournaments/models.py` | 26 | `Team.flag_url = URLField(blank=True)` — exists but empty |
| `apps/tournaments/models.py` | 66 | `Match.scheduled_at = DateTimeField(null=True, blank=True)` — exists but never populated |
| `apps/tournaments/models.py` | 48-52 | `Match.stage` TextChoices: group, r32, r16, qf, sf, third_place, final |
| `apps/tournaments/management/commands/load_wc2026.py` | 54 | `t.get("flag_url", "")` — flag_url always empty in JSON |
| `apps/tournaments/management/commands/load_wc2026.py` | 82-98 | Group match creation — no `scheduled_at` passed |
| `apps/tournaments/standings.py` | 73-85 | `_overall_sort` — tiebreak chain ends at FIFA ranking, no conduct score |
| `apps/tournaments/standings.py` | 176-189 | `rank_third_place_teams` — same, no conduct score |
| `apps/tournaments/services.py` | 78-90 | `_resolve_team` — bracket slot resolution logic |
| `apps/tournaments/services.py` | 93-192 | `build_predicted_knockout_bracket` — full bracket builder |
| `apps/leaderboard/scoring.py` | 11-21 | `DEFAULT_SCORING_CONFIG` — per-stage scoring dict |
| `apps/leaderboard/scoring.py` | 24-30 | `get_scoring_config` — fallback chain: pool → tournament → default |
| `apps/leaderboard/scoring.py` | 61-88 | `score_prediction` — no bracket-position bonus |
| `apps/leaderboard/tasks.py` | 10-41 | `recalculate_pool_scores` — triggered by Match post_save signal |
| `apps/leaderboard/views.py` | 113-148 | `ParticipantsView` — closest existing view to a monitoring view |
| `apps/pools/models.py` | 74 | `PoolTopScorerPick.player_name = CharField(max_length=100)` — free text |
| `apps/pools/models.py` | 84-103 | `LeaderboardEntry` — total_points, rank, previous_rank |
| `apps/predictions/views.py` | 131-164 | `KnockoutPredictionsView` — builds all stages together |
| `apps/predictions/views.py` | 211-244 | `PicksView` — derives champion from final bracket prediction |
| `apps/predictions/forms.py` | 28 | Argentine voseo: "Tenés que elegir un ganador..." |
| `apps/predictions/forms.py` | 38-39 | `TopScorerPickForm` — free text CharField |
| `apps/users/models.py` | 27-30 | User: `nickname` (unique), `email` (unique, USERNAME_FIELD) |
| `apps/users/urls.py` | 6-15 | Only 4 routes — no password reset |
| `apps/users/views.py` | 12-21 | `RegisterView` — no email verification |
| `templates/base.html` | 6 | Default title: "Quiniela 2026" |
| `templates/partials/nav.html` | 3 | Nav logo: emoji + "Quiniela 2026" text, no image |
| `templates/predictions/partials/knockout_stages.html` | 1-75 | All stages in one pass, no phase switcher |
| `templates/predictions/knockout.html` | 40-95 | IIFE for scroll/details state preservation around HTMX swaps |
| `templates/users/login.html` | 33 | Argentine voseo: "¿No tenés cuenta?" |
| `templates/users/register.html` | 35 | Argentine voseo: "¿Ya tenés cuenta?" |
| `templates/predictions/partials/group_standings.html` | (footer) | Argentine voseo: "Ingresá resultados para ver la tabla." |
| `data/wc2026.json` | — | Teams: name, fifa_code, fifa_ranking only — no flag_url, no match dates |
| `data/knockout_bracket.json` | — | Bracket slots: r32 through final, descriptor strings (A1, 3RD_N, win:SLOT) |
| `quiniela/settings/base.py` | 71 | `LANGUAGE_CODE = "es"`, `USE_I18N = True` — no .po files |
| `quiniela/settings/base.py` | 79-82 | `STATIC_URL = "/static/"`, `STATIC_ROOT`, no STATICFILES_DIRS |

---

## Open Questions

1. **Flag source**: Should `flag_url` be populated via Flagpedia CDN URLs in `wc2026.json`, or should a template filter map `fifa_code` → emoji flag at render time? Flagpedia uses ISO 3166-1 alpha-2 (2-letter), requiring a mapping from FIFA 3-letter codes.

2. **Match schedule data**: Where do match dates come from? The WC2026 schedule is publicly available. Should dates be added to `wc2026.json` directly, or a separate `schedule.json`? Format: ISO datetime strings.

3. **Pool monitoring view scope**: Should the view show picks from ALL members of a pool (including those who haven't submitted), or only submitted predictions?

4. **Bracket-position bonus**: Should this bonus apply retroactively when official bracket results are entered, or only be computed after the tournament? Requires a separate recalculation task.

5. **Third-place conduct tiebreaker UI**: Should this be an admin-only input (admin panel), or should users be able to see/interact with the tiebreaker? And does the user pick the specific qualifying teams, or just confirm the ranking?

6. **Player model vs. JSON fixture**: Should WC2026 players be stored in a DB table (`Player` model with FK to `Team`) or as a static JSON fixture served to the frontend? A DB model allows filtering by team and future stats; a JSON fixture is simpler to load.

7. **Password recovery security**: The email+nickname match approach (no token email) is simpler but means anyone who knows both fields can reset a password. Is this acceptable for this use case?

8. **Logo image format/placement**: What is the provided image? Where should it live (`static/images/`) and what filename/format?

9. **"La Gansa" scope**: Should "Quiniela 2026" be replaced everywhere (page titles, nav, all `{% block title %}` overrides), or kept in some places for context?

---

## Appendix

- **Architecture notes**: Pure monolith Django app. No JS framework — HTMX only. No i18n `.po` files; all strings hardcoded. Scoring is per-stage configurable via JSONField. The `predictions` and `leaderboard` apps both have empty `models.py`; actual models live in `apps/pools/models.py`.
- **Historical context**: `thoughts/miguel/research/2026-05-08-quiniela-project-architecture.md` — original architecture research covering domain model, feasibility, FIFA tiebreaker rules, and scoring config design.
- **Related research**:
  - `thoughts/miguel/research/2026-05-08-quiniela-project-architecture.md` — foundational architecture doc
