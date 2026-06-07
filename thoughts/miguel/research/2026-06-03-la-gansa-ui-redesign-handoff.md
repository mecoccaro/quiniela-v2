---
name: la-gansa-ui-redesign-handoff
description: Research on the La Gansa design handoff (design_handoff_lagansa/) and the current frontend codebase — maps design requirements to existing templates and identifies all changes needed, including the 3rd place tiebreaker validation fix.
metadata:
  date: 2026-06-03
  researcher: miguel
  git_commit: c0c666dbce6b7058aa0d7f6483f376459c63cd45
  branch: feature/fixes-and-features
  tags: [frontend, redesign, design-handoff, ui, templates, htmx, tailwind, third-place-validation]
  status: complete
---

# Research: La Gansa UI Redesign — Design Handoff + 3rd Place Validation Fix

## Research Question

What UI/UX changes does the `design_handoff_lagansa/` design prototype specify, how do they map to the current Django template codebase, and what needs to be implemented? Additionally, what is the 3rd place tiebreaker view missing in terms of validation?

## Summary

The design handoff is a high-fidelity React/HTML prototype defining a complete visual overhaul of the app under the "La Gansa" brand ("Fuego" theme: orange accent, cream background, DM Sans font). All six main views are redesigned. The current codebase uses Django templates + HTMX + Tailwind CDN with a green color scheme and plain number inputs. The redesign affects every template but **must keep all existing HTMX endpoints, form submissions, and data models intact** — only the visual layer changes. A separate bug fix is needed in `ThirdPlaceTiebreakerView.post()` where duplicate rank values are silently accepted.

---

## Detailed Findings

### 1. Design System — "Fuego" Theme

Defined in `design_handoff_lagansa/README.md` (lines 38-54) and implemented across all JSX files.

**Color tokens:**
| Token | Value | Current equivalent |
|---|---|---|
| `--accent` | `oklch(62% 0.22 28)` ≈ `#FF5100` | `green-600` (`#16a34a`) |
| `--accent-light` | `oklch(97% 0.06 28)` ≈ `#FFF2ED` | `green-50` |
| `--nav` | `#111111` | `bg-green-700` |
| `--nav-text` | `#FFFFFF` | `text-white` |
| `--bg` | `#F5F4EE` | `bg-gray-50` |
| `--surface` | `#FFFFFF` | `bg-white` |
| `--border` | `#E5E3DC` | `border-gray-200` |
| `--text` | `#111111` | `text-gray-800` |
| `--text-muted` | `#8A8877` | `text-gray-500` |
| `--success` | `#16A34A` | `text-green-700` |
| `--danger` | `#DC2626` | `text-red-600` |
| `--pending` | `#B45309` | `text-yellow-700` |

**Typography:** DM Sans from Google Fonts. `font-variant-numeric: tabular-nums` on all scores/points. Letter-spacing `-0.5px` to `-1px` on headings.

**Spacing:** Card `border-radius: 16px`, button `border-radius: 8px` (filled) / `100px` (pills), card `padding: 20-24px`, `box-shadow: 0 2px 12px rgba(0,0,0,0.04)`. Navbar height `56px`.

### 2. Current Template Inventory

| Template | Path | Tailwind color scheme |
|---|---|---|
| Base shell | `templates/base.html` | `bg-gray-50` body |
| Navbar | `templates/partials/nav.html` | `bg-green-700` |
| Dashboard | `templates/users/dashboard.html` | `bg-white` cards, `green-600` CTA |
| Group Stage | `templates/predictions/group_stage.html` | `bg-white`, `green-400` focus rings |
| Group Standings | `templates/predictions/partials/group_standings.html` | `bg-green-50`, `bg-yellow-50`, `bg-red-50` rows |
| Knockout | `templates/predictions/knockout.html` | `bg-gray-100`/`bg-green-600` tabs |
| Knockout Stages | `templates/predictions/partials/knockout_stages.html` | `green-400` focus, `green-600` indicators |
| Leaderboard | `templates/leaderboard/leaderboard.html` | Simple wrapper |
| Leaderboard Table | `templates/leaderboard/partials/leaderboard_table.html` | `bg-green-50` current user row |
| Pool Day | `templates/leaderboard/pool_day.html` | `bg-green-600` selected date, `green-700` hover |
| My Predictions | `templates/leaderboard/my_predictions.html` | `green-100` pts badge |
| 3rd Place Tiebreaker | `templates/predictions/third_place_tiebreaker.html` | `amber-50` info box, `green-600` submit |
| Picks | `templates/predictions/picks.html` | `green-600` confirm button |
| Submission Confirm | `templates/predictions/submission_confirm.html` | `green-600` submit |

### 3. View-by-View Design Requirements vs. Current State

#### 3.1 Navbar (`templates/partials/nav.html`)

**Current** (lines 2-22): Green-700 background, `logo.png` image, green-600 "Salir" button, max-w-4xl container.

**Design** (`gansa-components.jsx:5-37`):
- Background `#111111` (dark), height `56px`, `position: sticky, top: 0, z-index: 200`
- Logo: `32px` div with `conic-gradient` + 🦢 emoji, span "La Gansa" at `18px/800`
- Nav links: opacity 0.65, `13px`, no background
- Username: opacity 0.8
- "Salir" button: background `--accent` (orange), `border-radius: 6px`, `7px 16px` padding

**Keep intact:** `{% url 'dashboard' %}` link, logout form, user.nickname, show/hide auth links.

#### 3.2 Dashboard (`templates/users/dashboard.html`)

**Current** (lines 1-52): Simple `bg-white rounded-xl shadow` cards. No progress bar, no position number displayed prominently, status badges are `bg-yellow-100`/`bg-green-100`. Layout: flex row per card.

**Design** (`gansa-views.jsx:4-93`):
- Heading: `"Hola, [nombre] 👋"` at `32px/900`, letter-spacing `-1px`
- Subtitle: "Tus quinielas para el Mundial 2026" in `--text-muted`
- Pool cards (`16px` radius, `24px` padding):
  - Header row: pool name `20px/800` + position `#N` top-right in `--accent` at `28px/900`
  - Badges: "Enviado" (green), "Pendiente" (amber), "Posición #N" (orange)
  - **Progress bar**: `height: 6px`, orange fill, cream background, animated
  - Counter: `predictions / total` text above bar
  - Action buttons: filled orange "Predecir →" (pending) or outline "Mis picks" | "Tabla" | "Partidos" (submitted)

**Keep intact:** All `{% url %}` links (`group_predictions`, `my_predictions`, `leaderboard`, `pool_day`). The `membership.predictions_submitted` check. The `rank` variable.

#### 3.3 Group Stage (`templates/predictions/group_stage.html` + partials)

**Current** (group_stage.html:33-84):
- `<details>` collapsible elements, first one open
- Number `<input>` pairs for home/away scores
- HTMX `hx-post` on form `change` with `delay:400ms`
- Two-column grid: match inputs left, standings right

**Design** (`gansa-views.jsx:214-338`, `gansa-components.jsx:163-228`):
- Groups as white cards with clickable header (chevron rotates, mini progress bar per group)
- **GansaMatchRow**: `grid: 1fr 100px 1fr`, flag + name on each side, center "score pill" button
- **GansaScorePicker** (popover): absolute positioned, `340px` wide, `+/−` controls + preset grid + "Borrar"/"Listo" footer. Closes on click-outside.
- Phase tabs: "Fase de Grupos" (filled orange) | "Eliminatorias →" (outline, navigates to KO)
- Header counter: `X / total partidos predichos`

**Key interaction change:** Replace `<input type="number">` pairs with a score pill that opens a popover on click. The HTMX save still fires — can be triggered from the "Listo" button or on each +/- click.

**Keep intact:** `hx-post="{% url 'save_match_prediction' pool.pk match.pk %}"`, HTMX target `#standings-{{ group.letter }}`, the standings partial.

#### 3.4 Leaderboard (`templates/leaderboard/leaderboard.html` + `leaderboard_table.html`)

**Current**: Simple table with rank, player name, pts, status. Current user row is `bg-green-50`.

**Design** (`gansa-views.jsx:96-210`):
- **Podium** (top 3): flex row centered, order `2nd | 1st | 3rd`. Heights `80px | 104px | 64px`. Avatar circles (initials). Platform blocks with `border-radius: 8px 8px 0 0`. 1st place: orange platform + white text.
- **Table**: grid `48px 1fr 48px 56px 80px`. Columns: `#` | Player (avatar + name + "(vos)") | Trend ▲/▼ | Pts (20px/900 orange) | Status badge
- User row: `--accent-light` background
- Top 3 rank numbers in `--accent`, rest in `--text-muted`

**Keep intact:** `{% url 'leaderboard' pool.pk %}`, `entry.rank`, `entry.total_points`, `entry.rank_change`, `entry.user`, `submitted_ids`, HTMX polling `every 60s`.

#### 3.5 Pool Day / Partidos (`templates/leaderboard/pool_day.html`)

**Current**: Date nav (prev/next links), match list in `bg-white rounded-xl shadow p-5`, table per match with `<table>`.

**Design** (`gansa-views.jsx:499-666`):
- Date navigation: `←` button (disabled if first) + date label + `"DD/M →"` button
- **Match cards**: white `16px` radius card:
  - Header: flags + team names + time UTC + result pill (dark bg `--text` white text) or "Próximamente" badge
  - Predictions table: grid `1fr 120px 72px` (Usuario | Predicción | Puntos)
  - Header row: `--bg` background, uppercase 11px labels
  - Current user row: `--accent-light`
  - Points badges: 3pts green, 1pt orange, 0pts gray
- **Date strip** at bottom: pills for each date, `opacity: 0.45` for dates without matches

**Keep intact:** `?date=` query param navigation, `match_data` context, `p.prediction.points_awarded`, `p.user.nickname`, `available_dates`.

#### 3.6 My Predictions (`templates/leaderboard/my_predictions.html`)

**Current**: Stage-grouped sections with `bg-white rounded-xl shadow divide-y`, simple flex rows.

**Design** (`gansa-views.jsx:669-849`):
- Header: "Mis predicciones" + "Enviado" badge + "🔒 Bloqueado" badge (red) + pool name
- Total pts top-right in `--accent`
- **Sections as white cards** with section title header, pick rows inside
- Pick row: flag emoji + team names + optional penalty note in orange + score `X — Y` + pts badge

**Keep intact:** `stages` context var, `pred_data.pred`, `champion_pick`, `top_scorer_pick`, `membership.predictions_submitted`.

#### 3.7 Knockout (`templates/predictions/knockout.html` + `knockout_stages.html`)

**Current**: Round tabs with JS `switchKoStage()`, `<details>` per stage, number inputs in HTMX forms, scroll/state restoration logic.

**Design** (`gansa-views.jsx:413-496`):
- Same round tabs (already implemented)
- **New: Lista / Árbol segmented toggle** (right side of tab row)
- Lista view: white card with stage header + match list
- **Árbol view** (`GansaBracketTree`, gansa-views.jsx:345-411): absolute-positioned cards + SVG connector lines. Very complex — pure client-side JS, no HTMX. Requires separate implementation.
- Match rows in lista: same `GansaMatchRow` component pattern

**Keep intact:** HTMX save forms (`hx-post="{% url 'save_knockout_prediction' %}"`), scroll restore JS, `switchKoStage()`, `predictions_submitted` check.

### 4. Third Place Tiebreaker — Validation Gap

**File:** `apps/predictions/views.py`, `ThirdPlaceTiebreakerView.post()`, lines 203-214.

**Current behavior:**
```python
def post(self, request, pool_id):
    tied_teams = get_conduct_tied_thirds(request.user, self.pool)
    for team in tied_teams:
        rank_val = request.POST.get(f"rank_{team.pk}")
        if rank_val:
            ThirdPlaceTiebreakerPick.objects.update_or_create(...)
    return redirect("knockout_predictions", pool_id=self.pool.pk)
```

**Problems:**
1. If `rank_val` is empty (user didn't select), the pick is simply skipped — no error
2. If two teams get the same rank (e.g., both set to "1"), both are saved without any error
3. The template (`third_place_tiebreaker.html:41-50`) shows `<select>` with `required` but all rank values 1..N appear for every team, making duplicates trivially easy

**Fix needed in `ThirdPlaceTiebreakerView.post()`:**
```python
# After collecting all submitted ranks:
submitted_ranks = []
for team in tied_teams:
    rank_val = request.POST.get(f"rank_{team.pk}")
    if not rank_val:
        # missing rank → re-render with error
    submitted_ranks.append(int(rank_val))

if len(submitted_ranks) != len(set(submitted_ranks)):
    # duplicate ranks → re-render with error
```

The template also needs to display a validation error message when returned.

### 5. Design Errors / Deviations to Ignore

Per the README and user instructions, these design elements have errors that should NOT be implemented:
- Mock team names (e.g., "Estados Unidos" groups, specific bracket matchups) — keep actual DB data
- Mock player names in "Mis Picks" (e.g., "Francesco Totti") — keep actual predictions
- Mock pool names ("mondialeTest", "segundoTest") — keep actual pool names from DB
- The `tweaks-panel.jsx` file — prototype only, not needed in production

---

## Code References

| Component | File | Lines |
|---|---|---|
| ThirdPlaceTiebreakerView.post() | `apps/predictions/views.py` | 203-214 |
| ThirdPlaceTiebreakerView.get() | `apps/predictions/views.py` | 191-201 |
| GroupPredictionsView | `apps/predictions/views.py` | 44-98 |
| SaveMatchPredictionView | `apps/predictions/views.py` | 101-134 |
| KnockoutPredictionsView | `apps/predictions/views.py` | 139-179 |
| Navbar template | `templates/partials/nav.html` | 1-22 |
| Dashboard template | `templates/users/dashboard.html` | 1-52 |
| Group Stage template | `templates/predictions/group_stage.html` | 1-107 |
| Group Standings partial | `templates/predictions/partials/group_standings.html` | 1-42 |
| Knockout template | `templates/predictions/knockout.html` | 1-152 |
| Knockout Stages partial | `templates/predictions/partials/knockout_stages.html` | 1-78 |
| Leaderboard table partial | `templates/leaderboard/partials/leaderboard_table.html` | 1-45 |
| Pool Day template | `templates/leaderboard/pool_day.html` | 1-140 |
| My Predictions template | `templates/leaderboard/my_predictions.html` | 1-95 |
| 3rd Place template | `templates/predictions/third_place_tiebreaker.html` | 1-73 |
| GansaScorePicker (design ref) | `design_handoff_lagansa/gansa-components.jsx` | 72-160 |
| GansaMatchRow (design ref) | `design_handoff_lagansa/gansa-components.jsx` | 163-228 |
| GansaGroupStandings (design ref) | `design_handoff_lagansa/gansa-components.jsx` | 250-283 |
| GansaBracketTree (design ref) | `design_handoff_lagansa/gansa-views.jsx` | 345-411 |
| Design tokens | `design_handoff_lagansa/README.md` | 37-79 |

---

## Consolidated Change List

### Scope: New Git Branch

Create branch `feature/la-gansa-ui-redesign` from current `feature/fixes-and-features`.

### Phase 1 — Design System Foundation

1. **`templates/base.html`**: Add `<link>` for DM Sans from Google Fonts. Add `<style>` block with CSS custom properties (`--accent`, `--bg`, `--surface`, `--border`, `--text`, `--text-muted`, etc.) for the Fuego theme. Keep Tailwind CDN.

### Phase 2 — Global Components

2. **`templates/partials/nav.html`**: Dark `#111111` navbar. Orange accent "Salir" button. Keep logo.png or replace with CSS logo. Keep all Django template logic.

### Phase 3 — Dashboard

3. **`templates/users/dashboard.html`**: Redesign pool cards — progress bar, position badge top-right, new badge pills, filled/outline action buttons.

### Phase 4 — Group Stage

4. **`templates/predictions/group_stage.html`**: Replace `<details>` with clickable div headers (chevron + mini progress bar). Add ScorePicker JS component. Replace `<input type="number">` pairs with clickable score pills. Keep all HTMX attributes.
5. **`templates/predictions/partials/group_standings.html`**: Update colors to match design tokens (orange accent for top-2 rows instead of green-50/yellow-50/red-50).

### Phase 5 — Leaderboard

6. **`templates/leaderboard/leaderboard.html`**: Add podium section above table.
7. **`templates/leaderboard/partials/leaderboard_table.html`**: New grid layout, avatar initials, trend indicators, orange pts, accent-light current user row.

### Phase 6 — Pool Day

8. **`templates/leaderboard/pool_day.html`**: Redesigned match cards, new predictions grid, points badges, date strip at bottom.

### Phase 7 — My Predictions

9. **`templates/leaderboard/my_predictions.html`**: Redesigned header (badges + pts counter), sectioned white cards, pick rows with flags.

### Phase 8 — Knockout

10. **`templates/predictions/knockout.html`**: Add Lista/Árbol toggle. Implement bracket tree view as HTML+JS (using absolute positioning + SVG).
11. **`templates/predictions/partials/knockout_stages.html`**: Redesign match rows to GansaMatchRow style (score pill + ScorePicker popover, keeping HTMX forms).

### Phase 9 — Third Place Tiebreaker Validation Fix

12. **`apps/predictions/views.py`** (`ThirdPlaceTiebreakerView.post()`): Add validation — all teams must have a rank selected, and all ranks must be unique. Re-render form with error on failure.
13. **`templates/predictions/third_place_tiebreaker.html`**: Add error message display area.
