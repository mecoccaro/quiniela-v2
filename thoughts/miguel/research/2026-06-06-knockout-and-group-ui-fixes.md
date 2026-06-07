---
name: knockout-and-group-ui-fixes
description: Research on group-stage randomize bug, knockout lista/arbol views, arbol sizing, score saving, tie winner selection, and phase tabs removal
metadata:
  type: research
  date: 2026-06-06
  researcher: miguel
  status: complete
  tags: [predictions, knockout, group-stage, htmx, bracket, ui]
---

# Research: Group & Knockout UI Fixes

## Research Question

Six issues to address:
1. Randomize button in group phase saves too fast → ko-link appears but server redirects back
2. Remove the "Lista" view from knockouts, keep only "Árbol"
3. Arbol view window needs to be wider/larger
4. Arbol scores not saved until second click
5. Add tie winner selection inside the arbol
6. Remove phase-selection tabs in knockouts, show a simple title instead

---

## Issue 1 — Randomize: ko-link appears but server redirects back

### Root cause

`randomizeAll` (`templates/predictions/group_stage.html:187–215`) sets all input values synchronously and calls `updatePill` for each match, which in turn calls `_updateProgress` and shows `#ko-link` immediately (client-side, line 167).

However, the HTMX saves are **batched and delayed**: 8 forms per 500 ms. With 48 group-stage matches, all 6 batches take ~3 s to finish.

When the user clicks the ko-link *before* all saves complete, `KnockoutPredictionsView.dispatch` (`apps/predictions/views.py:147–155`) runs a server-side count:

```python
user_group = Prediction.objects.filter(
    user=request.user, pool=pool, match__stage=Match.Stage.GROUP
).count()
if user_group < total_group:
    messages.warning(...)
    return redirect("group_predictions", ...)
```

If even one batch hasn't landed yet, the redirect fires — bouncing the user back to the group page.

### Key locations

- Client: `group_stage.html:187–215` — `randomizeAll`, batch dispatch, ko-link update
- Client: `group_stage.html:155–168` — `_updateProgress` shows/hides ko-link
- Server: `views.py:147–155` — guard that counts saved predictions

### Fix approach

Track the number of pending HTMX saves. Only show (or enable) `#ko-link` after all pending requests have settled successfully. Use `htmx:beforeRequest` / `htmx:afterSettle` / `htmx:responseError` counters on group-stage forms.

---

## Issue 2 — Remove Lista view, keep only Árbol

### What exists

In `templates/predictions/knockout.html`:

| Element | Location | Purpose |
|---------|----------|---------|
| `#ko-tabs` div | lines 33–44 | Stage-selector buttons (Ronda de 32, Octavos…) |
| Lista/Árbol toggle | lines 46–56 | Two buttons calling `setKoView('list')` / `setKoView('bracket')` |
| `#ko-lista-content` | lines 59–71 | Wraps the lista HTML (includes knockout_stages.html) |
| `#ko-bracket-content` | line 75 | Hidden div, populated by `_ensureBracketTree()` |
| `setKoView(v)` | lines 95–107 | Toggles visibility between the two divs |

Currently lista is visible by default; bracket is hidden (`display:none`).

### Fix approach

- Remove the Lista/Árbol toggle buttons (lines 46–56)
- Remove `setKoView` function calls; keep the function body or drop it entirely
- Make `#ko-bracket-content` visible by default (remove `display:none`)
- Call `_ensureBracketTree()` on `DOMContentLoaded` instead of only when switching to bracket view
- Keep `#ko-lista-content` in the DOM (the hidden forms inside it are needed for HTMX saves and input state) but hide it visually — or keep rendering knockout_stages.html as a hidden backing layer

---

## Issue 3 — Arbol view too narrow/short

### Sizing constraints

The bracket container div (`knockout.html:75`):
```html
<div id="ko-bracket-content" style="display:none;border-radius:12px;overflow:auto;max-height:680px;">
```

`max-height:680px` caps the vertical space.

Inside `_ensureBracketTree()` (`knockout.html:226–229`):
```javascript
container.style.cssText = 'background:var(--bg);border-radius:16px;border:1px solid var(--border);overflow:auto;padding:8px 12px 12px;';
```
This overwrites the inline style set on the div, removing `max-height`. So the vertical constraint comes from the initial HTML attribute only (it is not re-applied in JS).

Computed total width (`totalW`):
```
R32W(128) + GAP(20) + IW(96) + GAP + IW + GAP + IW + GAP + FW(120) + GAP + IW + GAP + IW + GAP + IW + GAP + R32W + 1
= 1113 px
```

The inner `outer` div is absolutely sized to `totalW × totalH`, and `overflow:auto` on the container makes it horizontally scrollable. The page itself provides the horizontal context.

### Fix approach

- Remove `max-height:680px` from `knockout.html:75` (or set it much larger, e.g. `max-height:none`)
- Optionally add `width:100%` and `overflow-x:auto` so the bracket scrolls horizontally within the page rather than being clipped

---

## Issue 4 — Arbol scores not saved until second click

### Save flow in arbol

1. User clicks a card → `GansaPicker.open(card, 'hs-'+pk, 'as-'+pk, ...)` (`knockout.html:289`)
2. GansaPicker confirms → sets `pk.h.value`, `pk.a.value`, dispatches `change` with `bubbles:true` on `pk.h` (`score_picker.html:91–93`)
3. Callback `onDone` runs: `updateKoPill(pk)` + `_ensureBracketTree()` (`knockout.html:290`)
4. `_ensureBracketTree()` calls `container.innerHTML = ''` and rebuilds the bracket DOM

**Potential issue:** `_ensureBracketTree()` at step 4 rebuilds the bracket synchronously. The bracket container (`#ko-bracket-content`) is rebuilt completely, creating **new card elements with new `onclick` handlers**. This itself is fine. However:

The `change` event was dispatched at step 2 on the `hs-{pk}` input inside the `.ko-form` in `#ko-lista-content`. HTMX waits 400 ms (`hx-trigger="change delay:400ms"`) then fires the POST. The `hx-target="#ko-bracket"` response replaces the innerHTML of `#ko-bracket` (the lista wrapper) — this is fine.

**Actual bug**: `_ensureBracketTree()` is called *inside* `onDone` (synchronously), but then HTMX `afterSettle` also calls `_ensureBracketTree()` again (line 459). Between these two calls, the new score is visible in the arbol. The second `_ensureBracketTree()` re-reads `hs-{pk}` from the newly-swapped lista form HTML, which by then has the server's stored value. So the second render is correct.

The "second click" to save likely stems from **`_ensureBracketTree()` being called from `onDone` rebuilding the arbol DOM, destroying the current card before the HTMX request has been created**. When the bracket DOM is destroyed and rebuilt during `onDone`, any in-progress HTMX transactions on elements within the bracket container (if any) could be interrupted. However since the HTMX listeners are on the lista forms (not the bracket cards), this shouldn't matter.

More likely cause: the `GansaPicker` targets `hs-{pk}` and `as-{pk}` by `document.getElementById`. These inputs are in the lista forms. They persist through `_ensureBracketTree()` (which only rebuilds the bracket container). The `change` event on `hs-{pk}` should reach the `.ko-form` via bubbling. HTMX should fire.

One confirmed issue: if `ko-lista-content` is `display:none`, HTMX still processes it, **but** if `_ensureBracketTree()` is called synchronously inside `onDone` (between `dispatchEvent` and when HTMX gets to process the event queue), and rebuilds the outer div, it could flush some microtask queue or interrupt focus. Hard to pinpoint without devtools tracing.

**Safer fix**: Move `_ensureBracketTree()` out of the `onDone` callback — rely solely on `htmx:afterSettle` to trigger the re-render. This way the bracket only updates after the server confirms the save.

---

## Issue 5 — Tie winner selection in Árbol

### Current state

The winner-selection UI exists **only** in the lista view (`templates/predictions/partials/knockout_stages.html:30–44`):

```html
<div class="winner-wrap" style="display:none;...">
  <span>Ganador:</span>
  <select name="predicted_winner">
    <option value="">--</option>
    <option value="{{ slot.home_team.pk }}">...</option>
    <option value="{{ slot.away_team.pk }}">...</option>
  </select>
</div>
```

`syncWinner` (`knockout.html:375–387`) shows/hides this based on whether home score == away score. It is called on `htmx:afterSettle` and `DOMContentLoaded`.

The arbol `makeCard` function (`knockout.html:252–297`) renders only two score rows (home / away) with no winner UI at all. The HTMX save is triggered from the lista form via `hs-{pk}` change event — `predicted_winner` is sent from the hidden lista `<select>`, not from the arbol card.

### Fix approach

When the arbol user picks a tie score, the GansaPicker callback should open a secondary winner picker (or the GansaPicker itself should support a "winner" step for ties). The winner pick must be sent as `predicted_winner` in the HTMX form. Since the form lives in the lista, the `<select name="predicted_winner">` is already there — just hidden. After GansaPicker confirms a tie, call `syncWinner` on the relevant form to show the select, and show a small indicator on the arbol card (e.g. "pen: ?"). The user then selects the winner from the lista-select (or from an injected UI on the card after rebuild).

Alternatively: after confirm with tie, open a small inline winner picker on the arbol card. On selection, programmatically set the lista select value and dispatch `change` to trigger HTMX save.

---

## Issue 6 — Phase-selection tabs

### What exists

`knockout.html:33–44`:
```html
<div id="ko-tabs" style="...">
  {% for stage in stages %}
  <button class="ko-tab" onclick="switchKoStage('{{ stage.key }}')" ...>
    {{ stage.label }}
  </button>
  {% endfor %}
</div>
```

`switchKoStage(key)` hides/shows `[data-ko-stage]` divs in the lista HTML. Since we're removing the lista, these tabs serve no purpose for the arbol (which shows all stages simultaneously in a continuous bracket tree).

### Fix approach

Replace the entire `#ko-tabs` + view-toggle row (lines 32–57) with a simple heading:

```html
<h2 style="font-size:20px;font-weight:800;color:var(--text);margin-bottom:16px;">Eliminatorias</h2>
```

Remove `switchKoStage` function and `activeKoStage` variable (or leave them inert). Remove `ko-tab` styling and `#ko-tabs` div.

---

## Code Reference Map

| File | Lines | Topic |
|------|-------|-------|
| `templates/predictions/group_stage.html` | 23–24 | `#ko-link` visibility logic |
| `templates/predictions/group_stage.html` | 154–168 | `_updateProgress` — shows ko-link client-side |
| `templates/predictions/group_stage.html` | 187–215 | `randomizeAll` — batch HTMX dispatch |
| `apps/predictions/views.py` | 147–155 | Server-side guard before knockout page |
| `templates/predictions/knockout.html` | 33–57 | Stage tabs + Lista/Árbol toggle |
| `templates/predictions/knockout.html` | 59–76 | `#ko-lista-content` and `#ko-bracket-content` |
| `templates/predictions/knockout.html` | 95–107 | `setKoView()` |
| `templates/predictions/knockout.html` | 190–370 | `_ensureBracketTree()` — arbol renderer |
| `templates/predictions/knockout.html` | 252–297 | `makeCard()` — individual match card |
| `templates/predictions/knockout.html` | 283–294 | Card click → GansaPicker |
| `templates/predictions/knockout.html` | 372–406 | `syncWinner()`, `updateKoPill()` |
| `templates/predictions/knockout.html` | 447–461 | `htmx:afterSettle` → `_ensureBracketTree()` |
| `templates/predictions/partials/knockout_stages.html` | 30–44 | `.winner-wrap` with `predicted_winner` select |
| `templates/partials/score_picker.html` | 89–102 | `GansaPicker._confirm` and `_clear` |
