# La Gansa UI Redesign Implementation Plan

status: in-progress

## Overview

Implement the high-fidelity "La Gansa" UI redesign from `design_handoff_lagansa/` into the existing Django + HTMX + Tailwind CDN codebase. The redesign introduces the "Fuego" color system (orange accent, cream background, dark navbar, DM Sans font) and a new ScorePicker popover interaction for entering match scores. Includes a bug fix for the 3rd place tiebreaker validation allowing duplicate ranks.

- **Motivation**: Design handoff from Claude Design with complete visual spec; 3rd place validation gap reported in research
- **Related**: [`thoughts/miguel/research/2026-06-03-la-gansa-ui-redesign-handoff.md`], [`design_handoff_lagansa/README.md`], [`design_handoff_lagansa/gansa-components.jsx`], [`design_handoff_lagansa/gansa-views.jsx`]

## Current State Analysis

All templates use Tailwind CDN with a green color scheme (`green-600`/`green-700`). Score inputs are `<input type="number">` pairs in HTMX forms. Key files per feature:

- Base: `templates/base.html:1-48` — no CSS tokens, no custom font
- Navbar: `templates/partials/nav.html:2` — `bg-green-700`, `logo.png`, green "Salir" button
- Dashboard: `templates/users/dashboard.html:6-51` — flat cards, no progress bar, simple badges
- Group Stage: `templates/predictions/group_stage.html:33-84` — `<details>`, number inputs, HTMX `change delay:400ms`
- Leaderboard: `templates/leaderboard/partials/leaderboard_table.html:1-45` — plain table, no podium
- Pool Day: `templates/leaderboard/pool_day.html:37-138` — `<table>` inside match cards
- My Predictions: `templates/leaderboard/my_predictions.html:17-53` — flat div rows
- Knockout: `templates/predictions/knockout.html:27-50` — tabs only, no Lista/Árbol toggle
- 3rd Place validation gap: `apps/predictions/views.py:203-214` — no duplicate rank check

## Desired End State

Every view styled to the "Fuego" design tokens. ScorePicker popover replaces number inputs in group stage and knockout. Leaderboard shows visual podium. Pool day shows prediction table with color-coded points badges. 3rd place tiebreaker rejects duplicate rank submissions. Optional: full bracket tree view in knockout.

## What We're NOT Doing

- No progress bar on the dashboard (would require backend view change — deferred)
- No theme switching (only "Fuego" theme, no atletico/clasico)
- No editable bracket tree (Árbol view is read-only visualization — stretch Phase 10)
- No changes to models, URLs, Celery tasks, or scoring logic
- No changes to auth views (login, register, password recovery)
- No `tweaks-panel.jsx` (prototype-only, not needed)
- No changes to team names/player names — use actual DB data throughout

## Implementation Approach

- Add CSS custom properties to `base.html` once; all phases inherit them
- ScorePicker JS implemented as a reusable singleton in a `templates/partials/score_picker.html` partial, included by both group stage and knockout templates
- HTMX forms preserved exactly — only the score _display_ changes (hidden inputs replace visible ones); "Listo" button dispatches a `change` event to trigger HTMX
- Phases are ordered front-to-back by dependency: foundation → global → per-view
- Bracket tree phase is stand-alone and can be skipped without breaking anything

## Quick Verification Reference

```bash
uv run manage.py runserver          # dev server (manual visual check)
uv run pytest                       # all tests
uv run ruff check .                 # lint
uv run ruff format .                # format
```

---

## Phase 1: Design System Foundation

### Overview

`templates/base.html` gains DM Sans font import and a `<style>` block with all CSS custom properties for the Fuego theme. Body background changes from `bg-gray-50` to the cream `--bg`. This is the only change in this phase — all subsequent phases use these tokens via inline style or Tailwind's `[]` escape.

### Changes Required:

#### 1. Base Template
**File**: `templates/base.html`
**Changes**:
- Add `<link>` preconnect + `<link>` for DM Sans (weights 400–900) from Google Fonts in `<head>`
- Add `<style>` block with CSS custom properties:
  ```css
  :root {
    --accent:       oklch(62% 0.22 28);
    --accent-light: oklch(97% 0.06 28);
    --nav:          #111111;
    --nav-text:     #ffffff;
    --bg:           #F5F4EE;
    --surface:      #ffffff;
    --border:       #E5E3DC;
    --text:         #111111;
    --text-muted:   #8A8877;
    --success:      #16A34A;
    --success-light:#F0FFF4;
    --danger:       #DC2626;
    --danger-light: #FFF5F5;
    --pending:      #B45309;
    --pending-light:#FFFBEB;
  }
  body { font-family: 'DM Sans', system-ui, sans-serif; background: var(--bg); }
  .tabular-nums { font-variant-numeric: tabular-nums; }
  ```
- Remove `bg-gray-50` from `<body>` class (background now set via CSS var)

### Success Criteria:

#### Automated Verification:
- [x] `uv run ruff check .` passes (no Python changes in this phase)
- [x] `uv run pytest` passes (no logic changes)

#### Automated QA:
- [ ] Start dev server, open home page — verify DM Sans is loaded (check network tab: font file requested from fonts.googleapis.com)
- [ ] Verify `document.body.style` computed background is `#F5F4EE` (cream) not white/gray

#### Manual Verification:
- [ ] Page background is visually cream/warm (not pure white or gray-50)
- [ ] Text uses DM Sans (should look noticeably different from system-ui)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 1] design system foundation: CSS tokens + DM Sans`.

---

## Phase 2: Navbar

### Overview

`templates/partials/nav.html` redesigned to dark `#111111` background, sticky positioning, orange "Salir" CTA. All existing Django template logic (auth check, urls, user.nickname) preserved exactly.

### Changes Required:

#### 1. Navbar Partial
**File**: `templates/partials/nav.html`
**Changes**:
- Replace `bg-green-700` with inline `style="background:var(--nav); color:var(--nav-text)"`, `height:56px`, `position:sticky; top:0; z-index:200`
- Logo area: keep `{% url 'dashboard' %}` link. Replace `<img src="logo.png">` with a `32px` div using `conic-gradient(#E53E3E 0deg 90deg, #2B6CB0 90deg 180deg, #C6F135 180deg 270deg, #ED8936 270deg 360deg)` background + 🦢 emoji (8px font). Span "La Gansa" at `font-size:18px; font-weight:800; letter-spacing:-0.5px`
- Nav links (¿Cómo jugar?, FAQ): `opacity:0.65; font-size:13px; background:none; border:none`
- Username: `opacity:0.8; font-size:13px`
- "Salir" button: `background:var(--accent); color:#fff; border:none; border-radius:6px; padding:7px 16px; font-size:13px; font-weight:700`
- Keep logout `<form method="post">`, `{% csrf_token %}`, auth conditionals, all `{% url %}` references

### Success Criteria:

#### Automated Verification:
- [x] `uv run pytest` passes
- [x] `uv run ruff check .` passes

#### Automated QA:
- [ ] Dev server: navbar background is dark (`#111111`), not green
- [ ] Clicking logo navigates to dashboard
- [ ] "Salir" button appears orange

#### Manual Verification:
- [ ] Navbar looks visually correct: dark bg, white text, orange "Salir" CTA, 🦢 logo

**Implementation Note**: Commit: `[phase 2] navbar: dark theme + orange accent`.

---

## Phase 3: Dashboard

### Overview

`templates/users/dashboard.html` pool cards redesigned: position badge top-right, status/position pill badges (green/amber/orange), orange "Predecir →" CTA, outline "Mis picks / Tabla / Partidos" buttons. No progress bar (no backend change needed).

### Changes Required:

#### 1. Dashboard Template
**File**: `templates/users/dashboard.html`
**Changes**:
- Page heading: `font-size:32px; font-weight:900; letter-spacing:-1px` — "Hola, {{ user.first_name }} 👋"
- Subtitle: "Tus quinielas" in `var(--text-muted)` at `15px`
- Pool cards: `background:#fff; border-radius:16px; padding:24px; border:1px solid var(--border); box-shadow:0 2px 12px rgba(0,0,0,0.04)`. Column layout (flex-col), not flex-row
- Card header row: pool name `font-size:20px; font-weight:800` on left; rank `#N` (`font-size:28px; font-weight:900; color:var(--accent)`) on top-right (or blank if no rank)
- Tournament name: `font-size:13px; color:var(--text-muted)`
- Badge row: pill badges `border-radius:100px; font-size:12px; font-weight:700; padding:3px 10px`
  - Submitted → `background:var(--success-light); color:var(--success)` "Enviado"
  - Pending → `background:var(--pending-light); color:var(--pending)` "Pendiente"
  - Position → `background:var(--accent-light); color:var(--accent)` "Posición #N" (if rank exists)
- Action buttons row:
  - Pending: single filled button "Predecir →" → `{% url 'group_predictions' membership.pool.pk %}` in `background:var(--accent); color:#fff; border-radius:8px; padding:9px 20px; font-size:14px; font-weight:700`
  - Submitted: three outline buttons "Mis picks" / "Tabla" / "Partidos" → respective urls, `background:var(--bg); border:1.5px solid var(--border); border-radius:8px; padding:9px 18px; font-size:13px; font-weight:600`
- Keep all `{% url %}` links and the `{% if membership.predictions_submitted %}` check

### Success Criteria:

#### Automated Verification:
- [x] `uv run pytest` passes

#### Automated QA:
- [ ] Dashboard loads without errors; pool cards visible
- [ ] Orange "Predecir →" button visible for pending pool; outline buttons for submitted pool
- [ ] Position badge displays "#N" in orange when rank exists

#### Manual Verification:
- [ ] Card layout visually matches design spec (column, not row; badges above buttons)
- [ ] Cream page background + white cards visible

**Implementation Note**: Commit: `[phase 3] dashboard: pool cards redesign`.

---

## Phase 4: Group Stage + ScorePicker

### Overview

Most complex phase. Produces: (1) a reusable ScorePicker vanilla-JS singleton in `templates/partials/score_picker.html`, (2) redesigned `templates/predictions/group_stage.html` using score pills + ScorePicker, (3) updated `templates/predictions/partials/group_standings.html` with orange-accented top-2 rows.

### Changes Required:

#### 1. ScorePicker Partial (new file)
**File**: `templates/partials/score_picker.html`
**Changes** (new file — pure `<script>` tag, no HTML):
```javascript
// Singleton ScorePicker popover
// API: window.GansaPicker.open(btn, homeInputId, awayInputId, homeName, awayName, onDone)
//      window.GansaPicker.close()
```
Implementation details:
- One `<div id="gansa-picker">` appended to `<body>` on first use
- Sections: fine control (+/− for home, separator, +/− for away), presets grid, footer (Borrar / Listo)
- `open(btn, homeInputId, awayInputId, homeName, awayName, onDone)`:
  - Reads current values from `document.getElementById(homeInputId).value`
  - Positions picker `position:fixed` near `btn.getBoundingClientRect()` with viewport clamping
  - Renders preset pills: `[[0,0],[1,0],[0,1],[1,1],[2,0],[0,2],[2,1],[1,2],[2,2],[3,0],[0,3],[3,1],[1,3],[3,2],[2,3],[4,0],[0,4],[4,1],[1,4]]`
  - Mousedown listener on `document` → close if outside picker
- `close()`: hides picker
- `confirm()`: writes h/a values to the two hidden inputs, dispatches `new Event('change', {bubbles:true})` on homeInput, calls `onDone()`, closes
- "Borrar": sets both inputs to `""`, dispatches change, closes
- All styling uses inline CSS matching design tokens (no Tailwind classes — picker is in body context)

Include in `templates/base.html` at bottom of `<body>`: `{% include "partials/score_picker.html" %}`

#### 2. Group Stage Template
**File**: `templates/predictions/group_stage.html`
**Changes**:
- Replace `<details>` with clickable `<div class="group-card">`:
  - Header: group name + "X/6 partidos" + mini progress bar (80px wide, 5px tall, orange fill) + chevron `›` that rotates 90° when open
  - State managed via `data-open` attribute + JS toggle
  - Card: `background:#fff; border-radius:16px; border:1px solid var(--border); box-shadow:0 2px 8px rgba(0,0,0,0.04); overflow:hidden`
- Phase tabs above groups:
  - "Fase de Grupos" filled pill (orange, active)
  - "Eliminatorias →" outline pill → `{% url 'knockout_predictions' pool.pk %}`
- Header counter: "{{ total_predicted }} / {{ total_matches }} partidos predichos" (top right, orange number)
- Each match row: `display:grid; grid-template-columns:1fr 100px 1fr; align-items:center`
  - Home: flag emoji + name, right-aligned
  - Score pill: `<button class="score-pill" data-match-id="{{ match.pk }}">` — shows `X : Y` or `– : –`
  - Away: flag emoji + name, left-aligned
- Hidden HTMX form per match (replaces visible form):
  ```html
  <form id="score-form-{{ match.pk }}"
        hx-post="{% url 'save_match_prediction' pool.pk match.pk %}"
        hx-target="#standings-{{ group.letter }}"
        hx-swap="outerHTML"
        hx-trigger="change delay:400ms"
        hx-indicator="#spinner-{{ match.pk }}">
    {% csrf_token %}
    <input type="hidden" id="hs-{{ match.pk }}" name="predicted_home_score"
           value="{{ pred.predicted_home_score|default_if_none:'' }}">
    <input type="hidden" id="as-{{ match.pk }}" name="predicted_away_score"
           value="{{ pred.predicted_away_score|default_if_none:'' }}">
  </form>
  ```
- Score pill `onclick` calls `GansaPicker.open(this, 'hs-{{ match.pk }}', 'as-{{ match.pk }}', '{{ match.home_team.name|escapejs }}', '{{ match.away_team.name|escapejs }}', updatePill_{{ match.pk }})` where `updatePill_XX` is a closure that re-renders the pill text and mini group progress bar
- If `predictions_submitted`: score pill is non-clickable (just display), form inputs read-only
- Keep: `hx-headers` on body (already in base), JS `updateProgress()` function, `#progress-count`, `#ko-link`

#### 3. Randomize Button (Group Stage)
**File**: `templates/predictions/group_stage.html`
**Changes** (added alongside phase tabs row, before the groups list):
- Add a "🎲 Randomizar" button rendered only when `not predictions_submitted`:
  ```html
  <button id="randomize-btn" onclick="randomizeAll()" ...>🎲 Randomizar</button>
  ```
  Style: `background:var(--bg); border:1.5px solid var(--border); border-radius:8px; padding:7px 16px; font-size:13px; font-weight:700; color:var(--text-muted); cursor:pointer`
- JS `randomizeAll()` function (client-side, no backend call):
  - Finds all hidden inputs matching `[id^="hs-"]` (home score inputs) and their paired `[id^="as-"]` (away score inputs)
  - For each pair: sets `.value` to `Math.floor(Math.random() * 6)` (0–5 inclusive)
  - Calls the match's `updatePill_XX()` closure to re-render the score pill
  - Dispatches `new Event('change', {bubbles:true})` on the home score input to trigger HTMX auto-save (each match saves independently with `delay:400ms`)
  - Note: since HTMX uses `delay:400ms`, randomizing all matches fires many saves — this is intentional and matches the existing per-match save behavior

#### 4. Group Standings Partial
**File**: `templates/predictions/partials/group_standings.html`
**Changes**:
- Top-2 rows: `background:var(--accent-light)` (was `bg-green-50`)
- 3rd row: no highlight (was `bg-yellow-50`)
- 4th row: no highlight (was `bg-red-50`)
- `Pts` column: `font-weight:800; color:var(--accent)`
- Position number in top-2: `color:var(--accent)` (was `text-gray-400`)
- Header row: `font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); letter-spacing:0.05em`

### Success Criteria:

#### Automated Verification:
- [x] `uv run pytest` passes (no logic changes)
- [x] `uv run ruff check .` passes

#### Automated QA:
- [ ] Group stage page loads with all groups collapsed (except first open)
- [ ] Clicking a group header toggles it open/closed (chevron rotates)
- [ ] Clicking a score pill opens the ScorePicker popover
- [ ] ScorePicker +/− buttons change the displayed score
- [ ] Clicking a preset pill selects it and shows active state
- [ ] Clicking "Listo" closes picker and triggers HTMX save (group standings partial refreshes)
- [ ] Clicking "Borrar" clears score and triggers HTMX save
- [ ] Click outside picker closes it
- [ ] Group standings show orange accent for top-2 rows after scores are entered
- [ ] Progress counter (`X / total`) updates as scores are entered

#### Manual Verification:
- [ ] ScorePicker is positioned correctly near the clicked pill (not off-screen on mobile)
- [ ] Phase tabs ("Fase de Grupos" filled, "Eliminatorias →" outline) look correct
- [ ] Submitted pool: score pills are non-clickable, values shown in read-only style

**Implementation Note**: Commit: `[phase 4] group stage: ScorePicker popover + redesigned match rows`.

---

## Phase 5: Leaderboard

### Overview

`templates/leaderboard/leaderboard.html` gains a visual podium for top-3. `templates/leaderboard/partials/leaderboard_table.html` redesigned with avatar initials, orange points column, accent-light current-user row, and numeric trend indicators. HTMX polling preserved.

### Changes Required:

#### 1. Leaderboard Page
**File**: `templates/leaderboard/leaderboard.html`
**Changes**:
- Add podium section above `{% include leaderboard_table %}` when `entries|length >= 3`:
  ```
  Display order: entries.1 (2nd) | entries.0 (1st) | entries.2 (3rd)
  Heights: 80px | 104px | 64px
  ```
  - Avatar circle `44px` with initials `{{ entry.user.nickname|slice:":2"|upper }}`, orange bg for 1st
  - Platform block `border-radius:8px 8px 0 0`, orange for 1st, `var(--accent-light)` for 2nd/3rd
  - Name + pts on platform

#### 2. Leaderboard Table Partial
**File**: `templates/leaderboard/partials/leaderboard_table.html`
**Changes**:
- Keep HTMX attrs: `hx-get`, `hx-trigger="every 60s"`, `hx-target="this"`, `hx-swap="outerHTML"`
- Convert from `<table>` to CSS grid: `display:grid; grid-template-columns:48px 1fr 48px 56px 80px`
- Header row: `background:var(--bg)`, uppercase 11px labels: `#` | `JUGADOR` | `↕` | `PTS` | `ESTADO`
- Each entry row:
  - `#` column: `font-size:18px; font-weight:900; color:var(--accent)` for rank ≤ 3, `color:var(--text-muted)` for rest
  - `JUGADOR`: 32px avatar circle (initials, orange for current user, varied colors for others) + nickname + "(vos)" tag
  - `↕`: `▲N` green / `▼N` red / `—` using `entry.rank_change`; show absolute value
  - `PTS`: `font-size:20px; font-weight:900; color:var(--accent); font-variant-numeric:tabular-nums`
  - `ESTADO`: "Enviado" badge (green pill) or blank
- Current user row: `background:var(--accent-light)` (was `bg-green-50`)

### Success Criteria:

#### Automated Verification:
- [x] `uv run pytest` passes

#### Automated QA:
- [ ] Leaderboard page loads; podium visible when ≥ 3 entries
- [ ] Current user row shows in orange-tinted background
- [ ] Trend arrows display correctly (▲ green, ▼ red, — gray)
- [ ] HTMX poll every 60s does not break layout after refresh

#### Manual Verification:
- [ ] Podium heights are visually correct (1st tallest, 3rd shortest)
- [ ] Avatar initials readable

**Implementation Note**: Commit: `[phase 5] leaderboard: visual podium + redesigned table`.

---

## Phase 6: Pool Day

### Overview

`templates/leaderboard/pool_day.html` match cards redesigned: result pill (dark bg), "Próximamente" badge, predictions table with CSS grid and color-coded points badges, date strip pills at bottom.

### Changes Required:

#### 1. Pool Day Template
**File**: `templates/leaderboard/pool_day.html`
**Changes**:
- Page header: "Partidos" title (`28px/900`) + pool name in muted text
- Date nav: `←` link (disabled style if no prev_date) + current date label (`20px/800`) + `DD/M →` link for next
- Match cards: `background:#fff; border-radius:16px; border:1px solid var(--border); box-shadow:0 2px 8px rgba(0,0,0,0.04); overflow:hidden`
  - Card header: flags + team names + time UTC on left; result pill or badge on right
    - Result pill: `background:var(--text); color:#fff; border-radius:8px; padding:6px 16px; font-weight:900; font-size:17px; font-variant-numeric:tabular-nums`
    - No result: `"Próximamente"` badge `background:var(--pending-light); color:var(--pending); border-radius:100px`
  - Predictions table: `border-top:1px solid var(--border)`
    - Header row: `background:var(--bg); display:grid; grid-template-columns:1fr 120px 72px` — "USUARIO" | "PREDICCIÓN" | "PUNTOS" at 11px uppercase
    - Each participant row:
      - Current user (nickname == request.user.nickname): `background:var(--accent-light)`
      - Prediction: `font-weight:800; font-size:15px; font-variant-numeric:tabular-nums`
      - Points badge: `3pts` → green (`var(--success-light)` / `var(--success)`); `1pt` → orange (`var(--accent-light)` / `var(--accent)`); `0pts` → gray (`var(--bg)` / `var(--text-muted)`); pending → `—`
- Date strip at bottom: `display:flex; flex-wrap:wrap; gap:6px`. Each date a pill button/link
  - Active date: `background:var(--accent); color:#fff`
  - Other: `background:#fff; border:1.5px solid var(--border); color:var(--text-muted)`
  - Use existing `available_dates` context var

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest` passes

#### Automated QA:
- [ ] Pool day page loads; match cards visible with correct layout
- [ ] Date strip at bottom shows available dates; active date highlighted orange
- [ ] Result pill visible (dark bg) when match has official result

#### Manual Verification:
- [ ] Points badges color-coded correctly (green=3, orange=1, gray=0)
- [ ] Current user row has orange-tinted background
- [ ] "Próximamente" badge shows amber for future matches

**Implementation Note**: Commit: `[phase 6] pool day: match card redesign + date strip`.

---

## Phase 7: My Predictions

### Overview

`templates/leaderboard/my_predictions.html` gets a redesigned header with "Enviado"/"🔒 Bloqueado" badges and current points counter, plus sectioned white cards with pick rows showing flag emojis.

### Changes Required:

#### 1. My Predictions Template
**File**: `templates/leaderboard/my_predictions.html`
**Changes**:
- Header section (`display:flex; justify-content:space-between`):
  - Left: "Mis predicciones" (`28px/900`) + badges row
    - "Enviado" badge: `background:var(--success-light); color:var(--success)` (if submitted)
    - "🔒 Bloqueado" badge: `background:var(--danger-light); color:var(--danger)` (if submitted)
    - Pool name: `color:var(--text-muted); font-size:14px`
  - Right: current points `{{ total_points }}` (`28px/900; color:var(--accent)`) + "puntos actuales" label
  - Note: `total_points` not currently in context — compute in template: `{% for stage in stages %}{% for pred_data in stage.predictions %}{% if pred_data.pred.points_awarded %}{% endif %}{% endfor %}{% endfor %}` using template tag or pass `0` if no points. Use `{% with total=0 %}` accumulation or add a context var. **Simpler fallback**: if context doesn't have total_points, show the pool's `LeaderboardEntry.total_points` — check if `entry.total_points` is available. Otherwise omit the counter.
  - **Concrete approach**: Check `apps/leaderboard/views.py` — if `my_predictions` view has a `total_points` var, use it. If not, add it to the view context from `LeaderboardEntry.objects.filter(user=user, pool=pool).first()`.

#### 2. Section Cards
**Changes**:
- Each stage section: white card `border-radius:16px; border:1px solid var(--border); overflow:hidden; margin-bottom:16px`
- Section header: `padding:14px 20px; border-bottom:1px solid var(--border); font-size:17px; font-weight:800`
- Pick rows (`display:flex; align-items:center; padding:11px 20px; border-bottom:1px solid var(--border)`):
  - Match: `{{ pred_data.home_team.fifa_code|flag_emoji }} {{ pred_data.home_team }}` + "vs" + flag + away team
  - Optional penalty note: `color:var(--accent); font-size:11px` for KO matches with predicted_winner
  - Score: `font-weight:900; font-variant-numeric:tabular-nums`
  - Points badge: same color scheme as pool day (green=3pts, orange=1pt, gray=0pt)
- Champion + top scorer sections preserved with same card style

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest` passes

#### Automated QA:
- [ ] My predictions page loads; stage sections visible as white cards
- [ ] Submitted pool shows "Enviado" + "🔒 Bloqueado" badges in header
- [ ] Points badges appear next to predictions with official results

#### Manual Verification:
- [ ] Flag emojis visible next to team names in pick rows
- [ ] Points counter in top-right shows correct total

**Implementation Note**: Commit: `[phase 7] my predictions: header redesign + sectioned pick cards`.

---

## Phase 8: Knockout — Lista View

### Overview

`templates/predictions/knockout.html` gets a Lista/Árbol segmented toggle (Árbol placeholder, enabled in Phase 10). `templates/predictions/partials/knockout_stages.html` match rows redesigned with score pills + ScorePicker (reusing the Phase 4 partial). All HTMX forms and scroll restoration JS preserved.

### Changes Required:

#### 1. Knockout Template
**File**: `templates/predictions/knockout.html`
**Changes**:
- Add `{% include "partials/score_picker.html" %}` at bottom of content block (if not already in base.html)
- Add Lista/Árbol segmented toggle to the right of the round tabs row:
  ```html
  <div style="display:flex; gap:0; border-radius:8px; overflow:hidden; border:1.5px solid var(--border)">
    <button id="ko-view-list" onclick="setKoView('list')" ...>Lista</button>
    <button id="ko-view-bracket" onclick="setKoView('bracket')" ...>Árbol</button>
  </div>
  ```
  Active button: `background:var(--accent); color:#fff`; inactive: `background:#fff; color:var(--text-muted)`
- JS `setKoView(v)`: toggles between `#ko-lista-content` (visible) and `#ko-bracket-content` (hidden for now; enabled in Phase 10)
- Bracket tree placeholder div: `<div id="ko-bracket-content" style="display:none">` — Phase 10 fills this
- Wrap existing `#ko-bracket` in `<div id="ko-lista-content">`
- Round tabs styled: active tab `background:var(--accent); color:#fff; border-color:var(--accent)`; inactive `background:var(--surface); color:var(--text-muted); border:1.5px solid var(--border)`
- "Goleador y confirmar →" button: orange `background:var(--accent); color:#fff`

#### 1b. Randomize Button (Knockout)
**File**: `templates/predictions/knockout.html`
**Changes** (alongside the Lista/Árbol toggle row, rendered only when `not predictions_submitted`):
- Add a "🎲 Randomizar" button with the same styling as the group stage version
- JS `randomizeAllKo()` function:
  - Same approach: finds all `[id^="hs-"]` inputs on the knockout page, sets random 0–5 values
  - Re-renders each score pill text in-place (match IDs may differ in knockout — use same `updatePill_XX` closure pattern)
  - Dispatches `change` event on each home input to trigger HTMX auto-save
  - TBD slots (no actual match yet) are skipped if inputs are disabled or form is absent
  - Note: winner dropdowns (`syncWinner()`) are triggered automatically by the change event propagation — no extra call needed

#### 2. Knockout Stages Partial
**File**: `templates/predictions/partials/knockout_stages.html`
**Changes**:
- Stage card: `background:#fff; border-radius:16px; border:1px solid var(--border); overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,0.04)`
- Stage header: `display:flex; justify-content:space-between; padding:16px 20px; border-bottom:1px solid var(--border); font-size:18px; font-weight:800`
- Replace `<details>` with always-open div (tabs handle stage switching already)
- Each match slot row: `display:grid; grid-template-columns:1fr 100px 1fr; align-items:center; padding:14px 0; border-bottom:1px solid var(--border)`
  - Home team: flag + name right-aligned
  - Score pill (same structure as group stage, Phase 4)
  - Away team: flag + name left-aligned
  - Keep hidden HTMX form with `predicted_home_score`, `predicted_away_score` hidden inputs
  - Keep winner dropdown `select` for tied scores — position below the match row grid, shown/hidden by `syncWinner()` (keep existing JS)
- TBD slots: score pill shows `? : ?` in muted style, non-clickable

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check .` passes

#### Automated QA:
- [ ] Knockout page loads; round tabs switch between stages
- [ ] Lista/Árbol toggle visible; clicking Lista shows match rows, clicking Árbol shows placeholder
- [ ] ScorePicker opens from knockout match score pills
- [ ] "Listo" in picker triggers HTMX save; bracket state refreshes
- [ ] Winner dropdown appears when score is tied (existing `syncWinner()` JS still works)

#### Manual Verification:
- [ ] Round tabs styled correctly (orange active, outline inactive)
- [ ] Árbol toggle click shows a friendly placeholder message (e.g., "Vista árbol — próximamente")

**Implementation Note**: Commit: `[phase 8] knockout: lista view redesign + lista/árbol toggle`.

---

## Phase 9: Third Place Tiebreaker Validation Fix

### Overview

`ThirdPlaceTiebreakerView.post()` now validates that (1) every team has a rank assigned, and (2) no two teams share the same rank. Invalid submissions re-render the form with a clear error message.

### Changes Required:

#### 1. View — Validation Logic
**File**: `apps/predictions/views.py`
**Changes** to `ThirdPlaceTiebreakerView.post()` (lines 203-214):
```python
def post(self, request, pool_id):
    tied_teams = get_conduct_tied_thirds(request.user, self.pool)
    
    submitted = {}
    for team in tied_teams:
        rank_val = request.POST.get(f"rank_{team.pk}", "").strip()
        if not rank_val:
            return self._render_error(request, tied_teams, "Asigna un orden a todos los equipos.")
        submitted[team.pk] = int(rank_val)
    
    if len(submitted.values()) != len(set(submitted.values())):
        return self._render_error(request, tied_teams, "Cada equipo debe tener un orden diferente.")
    
    for team in tied_teams:
        ThirdPlaceTiebreakerPick.objects.update_or_create(
            user=request.user, pool=self.pool, team=team,
            defaults={"predicted_rank": submitted[team.pk]},
        )
    return redirect("knockout_predictions", pool_id=self.pool.pk)

def _render_error(self, request, tied_teams, error_msg):
    existing_picks = {
        p.team_id: p.predicted_rank
        for p in ThirdPlaceTiebreakerPick.objects.filter(user=request.user, pool=self.pool)
    }
    return render(request, "predictions/third_place_tiebreaker.html", {
        "pool": self.pool,
        "tied_teams": tied_teams,
        "existing_picks": existing_picks,
        "error": error_msg,
    })
```

#### 2. Template — Error Display
**File**: `templates/predictions/third_place_tiebreaker.html`
**Changes**:
- Add error banner after the info box (before the `<form>`):
  ```html
  {% if error %}
  <div class="bg-red-100 border border-red-300 text-red-800 rounded-xl p-4 mb-4 text-sm font-medium">
    ⚠ {{ error }}
  </div>
  {% endif %}
  ```
- Also update submit button colors from `bg-green-600` to `background:var(--accent)` for consistency
- No changes to form fields or `{% url %}` references

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest` passes (existing tests must still pass)
- [ ] `uv run ruff check .` passes
- [ ] New test: `uv run pytest tests/ -k tiebreaker` — write a short unit test for `ThirdPlaceTiebreakerView.post()` covering: (a) missing rank → 200 with error, (b) duplicate ranks → 200 with error, (c) valid unique ranks → redirect 302

#### Automated QA:
- [ ] Submit form with two teams at same position → error banner appears, no redirect
- [ ] Submit form leaving one team blank → error banner appears
- [ ] Submit form with all unique ranks → redirects to knockout

#### Manual Verification:
- [ ] Error message is readable and clearly explains what went wrong

**Implementation Note**: Commit: `[phase 9] 3rd place tiebreaker: reject duplicate rank submissions`.

---

## Phase 10: Bracket Tree View (Stretch)

### Overview

Implements the read-only "Árbol" view in knockout: a full bracket visualization using absolute positioning + SVG connector lines. Populated from the bracket context data serialized to JSON. Clicking "Árbol" toggle shows the tree; "Lista" shows the editable forms.

### Changes Required:

#### 1. Knockout Template — Bracket Data + Tree Renderer
**File**: `templates/predictions/knockout.html`
**Changes**:
- Serialize bracket data to JSON in template:
  ```django
  {{ bracket_json|json_script:"bracket-data" }}
  ```
  This requires the view to pass `bracket_json` — a JSON-safe dict of all stages with slot home/away names + predicted scores. Add to `KnockoutPredictionsView.get()` context:
  ```python
  import json
  bracket_json = {
      stage_key: [
          {
              "home": slot.home_team.name if slot.home_team else "TBD",
              "away": slot.away_team.name if slot.away_team else "TBD",
              "homeScore": slot.prediction.predicted_home_score if slot.prediction else None,
              "awayScore": slot.prediction.predicted_away_score if slot.prediction else None,
              "slotKey": slot.slot_key,
          }
          for slot in slots
      ]
      for stage_key, slots in ...
  }
  ```
- Fill the existing `<div id="ko-bracket-content">` placeholder with the JS tree renderer
- JS `renderBracketTree(containerId, data)` function (vanilla JS):
  - `CARD_W=178, CARD_H=62, RGAP=44, INTER_GAP=10, SLOT=72`
  - Compute center-Y positions per round algorithmically (halving from R32)
  - Render match cards as absolute-positioned divs: team names + scores
  - Render SVG connector lines (horizontal + vertical, `stroke:var(--border), strokeWidth:2`)
  - Container: `position:relative; overflow:auto; max-height:640px`
  - Read-only (no click handlers — scores are entered via Lista view)

#### 2. View Context Addition
**File**: `apps/predictions/views.py` — `KnockoutPredictionsView.get()`
**Changes**: Add `bracket_json` serialization to context (see above). Also update `SaveKnockoutPredictionView.post()` response to pass `bracket_json` if needed (only necessary if bracket tree re-renders on HTMX save — likely not, since tree is static snapshot).

### Success Criteria:

#### Automated Verification:
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check .` passes

#### Automated QA:
- [ ] Click "Árbol" toggle — bracket tree renders without JS errors
- [ ] All 5 rounds visible (R32 through Final) with correct relative positions
- [ ] SVG connector lines visible between rounds
- [ ] "TBD" slots render with muted style
- [ ] Click "Lista" → returns to editable match list

#### Manual Verification:
- [ ] Bracket tree is visually readable and resembles the design reference (`gansa-views.jsx:345-411`)
- [ ] No horizontal overflow on desktop at 960px+ width

**Implementation Note**: Commit: `[phase 10] knockout: bracket tree view (árbol)`.

---

## Appendix

- **Follow-up plans**: Progress bar on dashboard (requires `DashboardView` context enrichment — deferred)
- **Derail notes**:
  - `leaderboard_table.html` uses HTMX polling (`every 60s`). The podium is added outside the polled partial — after a poll, the table updates but the podium stays static. This is intentional (podium rarely changes mid-session). If needed, wrap both in one HTMX-polled block in a future plan.
  - The winner dropdown in knockout (`syncWinner()`) must remain in knockout_stages.html and keep working after the ScorePicker redesign. Phase 8 must not remove `syncWinner()`.
  - `my_predictions` view may need `total_points` added to context. Check `apps/leaderboard/views.py` before implementing Phase 7 — if already there, use it; if not, add `LeaderboardEntry` lookup.
  - Phase 10 requires a small view change to serialize bracket data to JSON. This is technically a backend change but minimal (no model/logic change, only serialization).
- **Branch**: `feature/la-gansa-ui-redesign` (from `feature/fixes-and-features`)
- **References**:
  - Research: `thoughts/miguel/research/2026-06-03-la-gansa-ui-redesign-handoff.md`
  - Design: `design_handoff_lagansa/README.md`, `gansa-components.jsx`, `gansa-views.jsx`
  - Prior plans: `thoughts/miguel/plans/2026-05-28-la-gansa-feature-batch.md`
