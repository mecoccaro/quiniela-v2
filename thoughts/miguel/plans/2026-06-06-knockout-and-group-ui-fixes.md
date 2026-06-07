# Knockout & Group Stage UI Fixes Implementation Plan

## Overview

Six targeted UI/JS fixes for the quiniela-v2 prediction portal: repair the group-stage randomize flow so the server gate doesn't bounce the user, clean up the knockout view (remove Lista, expand the Árbol, fix the phase tabs), fix a score-save race condition in the Árbol, and add tie-winner selection directly inside the Árbol cards.

- **Motivation**: UX bugs blocking users from progressing through the prediction flow; missing knockout interaction for draw predictions.
- **Related**: [`templates/predictions/group_stage.html`], [`templates/predictions/knockout.html`], [`templates/predictions/partials/knockout_stages.html`], [`templates/partials/score_picker.html`], [`apps/predictions/views.py`], `thoughts/miguel/research/2026-06-06-knockout-and-group-ui-fixes.md`
- **Status**: completed — branch `feature/knockout-group-ui-fixes` (5 commits, ready to merge)

---

## Current State Analysis

### Group stage randomize (`group_stage.html:187–215`)
`randomizeAll` sets all `hs-*`/`as-*` inputs synchronously then batches HTMX `change` dispatches (8 per 500 ms). `_updateProgress` (line 154) runs after each `updatePill` call and shows `#ko-link` as soon as all inputs are filled client-side — but the server hasn't persisted them yet. `KnockoutPredictionsView.dispatch` (`views.py:147–155`) counts DB rows; if any are missing it redirects back to the group page.

### Knockout view structure (`knockout.html`)
- **Lines 33–44**: `#ko-tabs` — stage-selector buttons (Ronda de 32, Octavos…) calling `switchKoStage(key)`.
- **Lines 46–56**: Lista/Árbol toggle — two buttons, `setKoView('list'/'bracket')`.
- **Lines 59–71**: `#ko-lista-content` — wraps `knockout_stages.html` include (forms, hidden inputs, `.winner-wrap`).
- **Line 75**: `#ko-bracket-content` — `display:none`, `max-height:680px`; populated by `_ensureBracketTree()`.
- **Line 290**: `_ensureBracketTree()` called inside GansaPicker `onDone` callback — causes a synchronous DOM rebuild before HTMX processes the change event, which can swallow the save.
- **Lines 95–107**: `setKoView()` controls visibility; `_ensureBracketTree()` only fires when switching to bracket view.

### Tie winner UI (`knockout_stages.html:30–44`)
`.winner-wrap` with `<select name="predicted_winner">` exists only in the lista forms. `syncWinner` (knockout.html:375–387) shows/hides it based on score equality. No equivalent UI exists in the Árbol cards (`makeCard`, lines 252–297).

---

## Desired End State

1. After clicking Randomizar on group stage, `#ko-link` appears only once **all** HTMX saves have confirmed (no premature navigation, no server redirect).
2. Knockout page shows **only** the Árbol — no Lista/Árbol toggle, no stage tabs; a plain "Eliminatorias" heading replaces them.
3. Árbol has no `max-height` constraint and is horizontally scrollable to show the full 1113 px bracket.
4. Clicking a score on the Árbol saves **on the first click** — no double-click needed.
5. When a tie score is set on an Árbol card, a winner picker appears inline on that card; selecting a winner sends `predicted_winner` in the HTMX save.
6. Phase tabs (`#ko-tabs`) are gone; `switchKoStage` is removed or inert.

---

## What We're NOT Doing

- No backend changes — all fixes are template/JS only.
- Not removing the lista form HTML (`knockout_stages.html`) from the DOM — the HTMX forms and hidden inputs must stay as the save mechanism.
- Not changing scoring logic, models, or API endpoints.
- Not touching the randomize button in the knockout page.

---

## Implementation Approach

- Work file-by-file: group_stage.html first (independent), then knockout.html (most changes), then knockout_stages.html (add winner-wrap trigger hook).
- Keep the lista forms in the DOM but `display:none` so HTMX and hidden inputs keep working.
- Replace the phase-tabs + toggle row with a heading in the same edit as hiding the lista.
- Fix the `_ensureBracketTree` race by moving it out of `onDone` entirely — `htmx:afterSettle` already re-renders the bracket.
- Implement tie-winner in the Árbol by injecting a small winner picker element into the card after a tie is confirmed, wiring it to the lista `<select>` via JS.

---

## Quick Verification Reference

```bash
uv run pytest                        # all tests
uv run ruff check .                  # lint
uv run manage.py runserver           # dev server for manual/visual checks
```

---

## Phase 1: Fix Group-Stage Randomize — Block ko-link Until All Saves Confirm

### Overview

`randomizeAll` will track in-flight HTMX requests and only show `#ko-link` after every save settles successfully. The ko-link is hidden and disabled during the save window.

### Changes Required:

#### 1. Group stage template JS
**File**: `templates/predictions/group_stage.html`

**Changes**:
- Add a `_pendingSaves` counter, incremented on `htmx:beforeRequest` for group forms and decremented on `htmx:afterSettle` / `htmx:responseError` for group forms.
- Modify `_updateProgress` to gate ko-link visibility on `filled === _total && _pendingSaves === 0`.
- In `randomizeAll`, set `_pendingSaves` to the total input count before dispatching events, so the gate closes immediately when randomize fires.
- On `htmx:afterSettle` for a group form, decrement `_pendingSaves`, then call `_updateProgress` to re-evaluate.
- On `htmx:responseError` for a group form, decrement `_pendingSaves` and show a brief error state.

**Implementation detail**: distinguish group-stage forms from knockout forms via the `hx-target` attribute (`#standings-*` targets) or a CSS class added to group forms.

### Success Criteria:

#### Automated Verification:
- [ ] Lint passes: `uv run ruff check .`
- [ ] Existing tests pass: `uv run pytest`

#### Automated QA:
- N/A — no browser test suite; verification is manual.

#### Manual Verification:
- [ ] Open group stage page; click Randomizar; confirm `#ko-link` is NOT visible immediately after click.
- [ ] Wait for all HTMX spinners to finish; confirm `#ko-link` becomes visible.
- [ ] Click `#ko-link`; confirm navigation reaches knockout page without a redirect/warning banner.

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 1] fix: randomize ko-link waits for all HTMX saves`.

---

## Phase 2: Knockout Structural Cleanup — Árbol Only, Correct Sizing, Fix Save Race

### Overview

The knockout page is refactored to show only the Árbol: phase tabs and the Lista/Árbol toggle are removed, the Árbol container loses its height cap, lista forms stay hidden in the DOM, and the `_ensureBracketTree` double-call on confirm is eliminated.

### Changes Required:

#### 1. Knockout template — header row
**File**: `templates/predictions/knockout.html`

**Changes** (lines 32–57):
- Replace the entire `<div style="display:flex;...">` row containing `#ko-tabs` and the Lista/Árbol toggle with a plain heading:
  ```html
  <h2 style="font-size:20px;font-weight:800;color:var(--text);margin-bottom:16px;">Eliminatorias</h2>
  ```
- Keep the randomize button (currently inside that row) — move it next to the heading or below it.

#### 2. Knockout template — lista/árbol visibility
**File**: `templates/predictions/knockout.html`

**Changes**:
- `#ko-lista-content` (line 59): add `style="display:none;"` (keep all child HTML — forms must stay in DOM for HTMX).
- `#ko-bracket-content` (line 75): remove `display:none` and `max-height:680px`; set `overflow-x:auto; width:100%;`.

#### 3. Knockout template — JS
**File**: `templates/predictions/knockout.html`

**Changes**:
- Remove or no-op `setKoView()` and `switchKoStage()` functions (or leave as empty stubs).
- Remove `activeKoStage` variable usage.
- In `DOMContentLoaded` handler (line 464): add `_ensureBracketTree()` call so the bracket renders on page load.
- In `htmx:afterSettle` handler (line 453): keep the existing `_ensureBracketTree()` call (line 459), but remove the `bracketEl.style.display !== 'none'` guard since bracket is always visible.
- In the GansaPicker `onDone` callback (line 290): remove the `_ensureBracketTree()` call — only keep `updateKoPill(String(pk))`. Bracket will re-render on `htmx:afterSettle`.

### Success Criteria:

#### Automated Verification:
- [ ] Lint passes: `uv run ruff check .`
- [ ] Existing tests pass: `uv run pytest`

#### Automated QA:
- N/A — no browser test suite; verification is manual.

#### Manual Verification:
- [ ] Open knockout page; confirm no Lista/Árbol toggle buttons are visible.
- [ ] Confirm no stage-selector tabs (`#ko-tabs`) are present.
- [ ] Confirm Árbol bracket renders immediately on page load without any click.
- [ ] Scroll bracket left-right to confirm full bracket visible without vertical clipping.
- [ ] Click an Árbol card, set a score, confirm it saves on the first confirmation (no second click).
- [ ] Visually confirm "Eliminatorias" heading replaced the old tab row.

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 2] feat: knockout árbol-only view, remove lista/tabs, fix sizing and save race`.

---

## Phase 3: Tie Winner Selection in the Árbol

### Overview

When a user confirms a draw score on an Árbol card, a winner-picker row appears inline on that card. Selecting a team writes to the backing lista `<select name="predicted_winner">` and triggers an HTMX save.

### Changes Required:

#### 1. Knockout template — `makeCard` function
**File**: `templates/predictions/knockout.html`

**Changes** inside `makeCard()` (lines 252–297):
- After rendering the two team rows, if `!_koSubmitted && match.matchPk`, inject a hidden `div.arbol-winner-row` inside the card:
  ```html
  <div class="arbol-winner-row" style="display:none; padding:3px 7px; border-top:1px solid var(--border);">
    <span style="font-size:10px;color:var(--text-muted);">Pen:</span>
    <button data-team="home" style="...">🏳 HOME</button>
    <button data-team="away" style="...">🏳 AWAY</button>
  </div>
  ```
- Populate team code/name from `match.homeCode`/`match.awayCode` on card creation.
- Wire each button's `onclick` to a new `_setKoWinner(matchPk, 'home'|'away')` function.

#### 2. Knockout template — `updateKoPill` / `onDone` callback
**File**: `templates/predictions/knockout.html`

**Changes**:
- After score is confirmed (in `updateKoPill` or via a post-confirm hook), call a new `_syncArbolWinnerRow(matchPk)`:
  - If scores are equal and both set, show `.arbol-winner-row` on the card (if card exists in DOM).
  - If scores differ or are empty, hide `.arbol-winner-row`.
- `_ensureBracketTree` already rebuilds all cards on `htmx:afterSettle` — this will re-render the winner row with correct initial visibility based on stored scores.

#### 3. New JS function — `_setKoWinner(matchPk, side)`
**File**: `templates/predictions/knockout.html`

**New function**:
```javascript
function _setKoWinner(matchPk, side) {
  // Find the lista <select name="predicted_winner"> inside the .ko-form for this match
  var form = document.querySelector('.ko-form [id="hs-' + matchPk + '"]');
  if (form) form = form.closest('.ko-form');
  if (!form) return;
  var sel = form.querySelector('select[name="predicted_winner"]');
  if (!sel) return;
  // side === 'home' → pick home team option; 'away' → pick away team option
  var opts = sel.querySelectorAll('option[value]:not([value=""])');
  sel.value = side === 'home' ? opts[0].value : (opts[1] ? opts[1].value : '');
  sel.dispatchEvent(new Event('change', { bubbles: true }));
}
```

#### 4. Árbol card re-render — winner row state after `htmx:afterSettle`
**File**: `templates/predictions/knockout.html`

**Changes** inside `makeCard()`:
- On card creation, check `hasScore && hScore === aScore` — if true, render `.arbol-winner-row` visible with the correct winner highlighted (read from `match.winnerCode` if available in bracket JSON, or leave both buttons unselected).
- Add `winnerCode` to the bracket JSON shape (`bracket_json` in views.py already exposes `predicted_winner` data — extend the JSON serialization if needed, or infer from lista select after render).

**Note on winner data in bracket JSON**: The `bracket_json` built in `KnockoutPredictionsView.get` (`views.py:176–193`) does not currently include `predicted_winner`. To highlight the selected winner button after re-render, add `"winnerPk": slot.prediction.predicted_winner_id if slot.prediction else None` to the JSON. This is a minimal, read-only addition — no model or URL change.

#### 5. `bracket_json` — add `winnerPk` field
**File**: `apps/predictions/views.py` (lines 181–193) and `apps/predictions/views.py` (lines 288–296, the save view's bracket JSON equivalent is `knockout_stages.html` not JSON — no change needed there)

**Change**: Add one field to the `bracket_json` dict comprehension in `KnockoutPredictionsView.get`:
```python
"winnerPk": slot.prediction.predicted_winner_id if slot.prediction else None,
```

### Success Criteria:

#### Automated Verification:
- [ ] Lint passes: `uv run ruff check .`
- [ ] Existing tests pass: `uv run pytest`

#### Automated QA:
- N/A — no browser test suite; verification is manual.

#### Manual Verification:
- [ ] Click an Árbol card, set a draw score (e.g. 1–1); confirm a winner-picker row appears on the card.
- [ ] Click a winner button; confirm it highlights and the HTMX spinner fires.
- [ ] Reload the page; confirm the card renders with winner row visible and the correct team highlighted.
- [ ] Set a non-draw score (e.g. 2–1); confirm winner row is hidden on that card.
- [ ] Confirm winner row buttons display correct team names/flags.

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 3] feat: tie winner selection in árbol cards`.

---

## Appendix

- **Follow-up plans**: none anticipated.
- **Derail notes**:
  - `bracket_json` in the knockout save response (`SaveKnockoutPredictionView`) returns `knockout_stages.html`, not JSON — no changes needed there for the winner row to work, since the page re-renders via `_ensureBracketTree` after settle and reads `bracket-data` (the page-load JSON, not the HTMX response).
  - The `#ko-bracket` HTMX swap (`hx-target="#ko-bracket", hx-swap="innerHTML"`) replaces lista forms. After settle, `_ensureBracketTree` re-reads `bracket-data` JSON from `#bracket-data` script tag — this is the **page-load** JSON, not updated by HTMX responses. Winner data in `bracket-data` won't update after HTMX saves without a page reload. For Phase 3 winner highlighting to work post-HTMX, `_setKoWinner` reads from the **lista select** (updated by HTMX response), not from `bracket-data`. This keeps things working without a page reload.
- **References**:
  - Research: `thoughts/miguel/research/2026-06-06-knockout-and-group-ui-fixes.md`
