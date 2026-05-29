---
status: in-progress
---

# La Gansa — Feature Batch Implementation Plan

## Overview

Batch of 10 features to evolve Quiniela 2026 into "La Gansa": visual improvements (flags, carousel, logo), UX improvements (neutral Spanish, searchable player picker, pool monitoring view), new scoring dimensions (bracket position bonus), edge case handling (conduct tiebreaker UI), and new auth module (password recovery).

- **Motivation**: Feature list from Miguel — round out the product before WC2026 kicks off
- **Related**: [`thoughts/miguel/research/2026-05-28-feature-batch-flags-knockout-monitoring-scoring-auth-branding.md`]

---

## Current State Analysis

- `Team.flag_url` exists (`apps/tournaments/models.py:26`) but is always `""` — never populated by loader or JSON
- Knockout view renders all rounds in one sequential partial (`knockout_stages.html`) with no phase-switching UI
- All UI strings are hardcoded in Argentine voseo (tenés, podés, hacé, etc.) in templates and Python forms — no `.po` files
- `Match.scheduled_at` exists (`models.py:66`) but loader never populates it — no date data in JSON
- Per-stage scoring config is fully implemented (`leaderboard/scoring.py:11-21`) via JSON fallback chain; no bracket-position bonus or conduct-score field exist
- `PoolTopScorerPick.player_name` is a free-text CharField; no player list/model
- Zero password reset routes — user model has `email` + `nickname` both unique
- "Quiniela 2026" hardcoded in 5 template locations; nav logo is text+emoji, no `<img>`

## Desired End State

- Every team display shows its country emoji flag
- Knockout bracket has a tab row letting users switch between rounds
- All UI text uses neutral Latin American Spanish
- Pool admins/members can browse picks by game date with a date switcher
- Scoring config updated to user-desired values with an additional bracket-position bonus dimension
- When third-place tie reaches conduct level, a UI lets the user manually rank tied teams
- Top scorer input is a searchable datalist populated from WC2026 squad list
- Password recovery via email + nickname match (no SMTP required)
- "La Gansa" brand name + logo image throughout

## What We're NOT Doing

- Django i18n `.po`/`.mo` translation files — strings stay hardcoded
- Email token-based password reset (SMTP not configured)
- Player DB model — static JSON fixture only
- 495-combination R32 third-place assignment table (remains rank-by-index)
- Real conduct score data entry for official results (admin enters via Django admin)

## Implementation Approach

- Phases ordered: quick/low-risk text changes first → data layer → new views → complex scoring last
- Flags via Django template filter (no CDN dependency, no model change, no migration)
- Knockout carousel via client-side CSS show/hide tabs; HTMX swap already replaces `#ko-bracket` innerHTML so tab state preserved in JS outside that element
- Match schedule added to `data/wc2026.json` as a `"schedule"` array; loader updated to populate `Match.scheduled_at`
- Players stored in `data/players.json` (static fixture); loaded in `PicksView` context
- Bracket position bonus stored as `Prediction.slot_bonus_awarded`; totaled in `_recalculate_leaderboard`
- Conduct tiebreaker: new `ThirdPlaceTiebreakerPick` model + new view in prediction flow

## Quick Verification Reference

```bash
uv run pytest                          # full test suite
uv run ruff check .                    # lint
uv run ruff format . --check           # format check
uv run manage.py runserver             # dev server
```

---

## Phase 1: Branding, Language & Logo

### Overview

Replace all "Quiniela 2026" references with "La Gansa", add logo image to the nav bar, and replace every Argentine voseo form with neutral Latin American Spanish across all templates and Python code. No migrations or new files except the static logo.

### Changes Required:

#### 1. Rename brand to "La Gansa"
**Files**: `templates/base.html`, `templates/partials/nav.html`, `templates/users/login.html`, `templates/users/register.html`, `templates/users/dashboard.html`
**Changes**:
- `base.html:6` — `{% block title %}Quiniela 2026{% endblock %}` → `{% block title %}La Gansa{% endblock %}`
- `nav.html:3` — `⚽ Quiniela 2026` → `<img src="{% static 'images/logo.png' %}" ...> La Gansa` (see item 2)
- `login.html:3` — title → `Ingresar — La Gansa`
- `register.html:3` — title → `Registrarse — La Gansa`
- `dashboard.html:3` — title → `Panel — La Gansa`

#### 2. Add logo image
**Files**: `quiniela/settings/base.py`, `static/images/logo.png` (provided by user), `templates/partials/nav.html`
**Changes**:
- `settings/base.py` — add `STATICFILES_DIRS = [BASE_DIR / "static"]` after `STATIC_ROOT`
- Create `static/images/` directory; place provided logo image as `logo.png`
- `nav.html` — add `{% load static %}` at top; replace emoji+text with `<img src="{% static 'images/logo.png' %}" alt="La Gansa" class="h-8 w-auto inline"> La Gansa`

#### 3. Neutral Spanish (templates)
**Files**: `templates/users/login.html`, `templates/users/register.html`, `templates/users/dashboard.html`, `templates/predictions/group_stage.html`, `templates/predictions/knockout.html`, `templates/predictions/submission_confirm.html`, `templates/partials/howto_modal.html`, `templates/partials/faq_modal.html`, `templates/predictions/partials/group_standings.html`
**Changes** (exhaustive list):

| File | Line | Before | After |
|------|------|--------|-------|
| `login.html` | 34 | `¿No tenés cuenta?` | `¿No tienes cuenta?` |
| `register.html` | 35 | `¿Ya tenés cuenta?` | `¿Ya tienes cuenta?` |
| `dashboard.html` | 46 | `no estás en ninguna quiniela` | `no estás en ninguna quiniela` *(acceptable, keep)* |
| `dashboard.html` | 48 | `Pedile al administrador` | `Pídele al administrador` |
| `group_stage.html` | 27 | `Solo podés ver los resultados` | `Solo puedes ver los resultados` |
| `knockout.html` | 23 | `Solo podés ver los resultados` | `Solo puedes ver los resultados` |
| `submission_confirm.html` | 38 | `completá tu Final` | `completa tu Final` |
| `howto_modal.html` | 23 | `Seguí prediciendo`, `elegí también` | `Sigue prediciendo`, `elige también` |
| `howto_modal.html` | 38 | `Confirmá y enviá` | `Confirmar y enviar` |
| `howto_modal.html` | 39 | `tenés todo completo, hacé click` | `tienes todo completo, haz clic` |
| `howto_modal.html` | 44 | `Revisá la tabla`, `cómo vas` | `Revisa la tabla`, `cómo vas` |
| `faq_modal.html` | 13 | `cuando vos mismo las confirmás`, `no podés modificarlas`, `Asegurate` | `cuando las confirmas`, `no puedes modificarlas`, `Asegúrate` |
| `faq_modal.html` | 23 | `Si predecís empate`, `tenés que elegir` | `Si predices empate`, `tienes que elegir` |
| `faq_modal.html` | 28 | `cuando confirmás y enviás` | `cuando confirmas y envías` |
| `faq_modal.html` | 33 | `completá todo el bracket` | `completa todo el bracket` |
| `group_standings.html` | footer | `Ingresá resultados para ver la tabla.` | `Ingresa resultados para ver la tabla.` |

#### 4. Neutral Spanish (Python)
**Files**: `apps/predictions/forms.py`, `apps/predictions/views.py`
**Changes**:
- `forms.py:28` — `"Tenés que elegir un ganador cuando el resultado es empate."` → `"Tienes que elegir un ganador cuando el resultado es empate."`
- `views.py:347` — `f"Faltan predicciones: tenés {user_predictions} de..."` → `f"Faltan predicciones: tienes {user_predictions} de..."`

### Success Criteria:

#### Automated Verification:
- [x] Lint passes: `uv run ruff check .`
- [x] Zero occurrences of voseo markers: `grep -rn "tenés\|podés\|hacé\|ingresá\|pedile\|elegí\|confirmá\|enviá\|revisá\|seguí" templates/ apps/ | grep -v ".pyc" | wc -l` → output must be `0`
- [x] Zero occurrences of old brand: `grep -rn "Quiniela 2026" templates/ apps/ | wc -l` → output must be `0`

#### Automated QA:
- [ ] Start server, navigate to `/login/` — page title is "Ingresar — La Gansa", logo image appears in nav
- [ ] Navigate to `/register/` — title is "Registrarse — La Gansa"
- [ ] Open "¿Cómo jugar?" modal — no voseo visible

#### Manual Verification:
- [ ] Logo image renders at correct size and looks correct in nav
- [ ] All renamed pages display "La Gansa" in browser tab

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 1] branding: rename to La Gansa, logo, neutral Spanish`.

---

## Phase 2: Country Emoji Flags

### Overview

A Django template filter `flag_emoji` converts any team's `fifa_code` (3-letter) to a country emoji flag (🇦🇷, 🇫🇷, etc.) using a FIFA→ISO2 mapping dict. Updated in every template where teams are displayed.

### Changes Required:

#### 1. Template filter
**File**: `apps/tournaments/templatetags/__init__.py` *(create empty)*
**File**: `apps/tournaments/templatetags/tournament_tags.py` *(create)*
**Changes**: Define `@register.filter flag_emoji(fifa_code)`:
```python
from django import template
register = template.Library()

FIFA_TO_ISO2 = {
    "ENG": "GB", "SCO": "GB", "WAL": "GB", "NIR": "GB",
    "KOR": "KR", "IRN": "IR", "KSA": "SA", "UAE": "AE",
    "CRC": "CR", "TRI": "TT", "CIV": "CI", "CMR": "CM",
    "NGA": "NG", "SEN": "SN", "GHA": "GH", "MAR": "MA",
    "TUN": "TN", "EGY": "EG", "ALG": "DZ", "RSA": "ZA",
    "PAN": "PA", "JAM": "JM", "HAI": "HT", "CUB": "CU",
    # All other teams: first 2 letters of fifa_code map to ISO2
}

@register.filter
def flag_emoji(fifa_code):
    if not fifa_code:
        return ""
    iso2 = FIFA_TO_ISO2.get(fifa_code, fifa_code[:2]).upper()
    return chr(0x1F1E6 + ord(iso2[0]) - ord('A')) + chr(0x1F1E6 + ord(iso2[1]) - ord('A'))
```

#### 2. Update group stage template
**File**: `templates/predictions/group_stage.html`
**Changes**: Add `{% load tournament_tags %}` at top. Replace bare team name with `{{ match.home_team.fifa_code|flag_emoji }} {{ match.home_team.name }}` for both home and away in match forms.

#### 3. Update knockout stages partial
**File**: `templates/predictions/partials/knockout_stages.html`
**Changes**: Add `{% load tournament_tags %}`. Replace `slot.home_team.name|default:"TBD"` with `{{ slot.home_team.fifa_code|flag_emoji }} {{ slot.home_team.name|default:"TBD" }}` (and same for away team).

#### 4. Update group standings partial
**File**: `templates/predictions/partials/group_standings.html`
**Changes**: Add `{% load tournament_tags %}`. Add `{{ team.fifa_code|flag_emoji }}` before `{{ team.name }}` in standings table rows.

#### 5. Update picks template
**File**: `templates/predictions/picks.html`
**Changes**: Add `{% load tournament_tags %}`. Add `{{ predicted_champion.fifa_code|flag_emoji }}` before champion name display.

#### 6. Update my predictions template
**File**: `templates/leaderboard/my_predictions.html`
**Changes**: Add `{% load tournament_tags %}`. Add flags wherever team names appear in prediction rows.

### Success Criteria:

#### Automated Verification:
- [x] Lint passes: `uv run ruff check .`
- [x] Tests pass: `uv run pytest`
- [x] Filter self-test: `uv run python -c "from apps.tournaments.templatetags.tournament_tags import flag_emoji; assert flag_emoji('ARG') == '🇦🇷'; assert flag_emoji('ENG') == '🇬🇧'; assert flag_emoji('KOR') == '🇰🇷'; print('OK')"` → `OK`

#### Automated QA:
- [ ] Start server, navigate to group stage predictions page — flags appear next to team names in match forms
- [ ] Navigate to knockout bracket page — flags appear next to team names in slots
- [ ] Navigate to picks page — champion display shows flag emoji

#### Manual Verification:
- [ ] Emoji flags render correctly on mobile (iOS/Android emoji support)
- [ ] "TBD" slots show no flag (empty string)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 2] add country emoji flags to all team displays`.

---

## Phase 3: Knockout Phase Carousel

### Overview

A tab row above the knockout bracket lets users click between R32 / R16 / QF / SF / Final. Each stage section gets a `data-stage` attribute; vanilla JS shows only the active stage. Tabs survive HTMX swaps because they live outside `#ko-bracket`.

### Changes Required:

#### 1. Add tabs to knockout page
**File**: `templates/predictions/knockout.html`
**Changes**:
- Above `<div id="ko-bracket">`, add a tab strip:
```html
<div id="ko-tabs" class="flex gap-2 mb-4 overflow-x-auto">
  {% for stage in stages %}
    <button
      onclick="switchKoStage('{{ stage.key }}')"
      id="ko-tab-{{ stage.key }}"
      class="ko-tab px-3 py-1.5 rounded text-sm font-medium whitespace-nowrap
             bg-gray-100 text-gray-700 hover:bg-green-100 hover:text-green-800"
      data-stage="{{ stage.key }}">
      {{ stage.label }}
    </button>
  {% endfor %}
</div>
```
- Active tab style: add `ko-tab-active` CSS class (`bg-green-600 text-white`)

#### 2. Add `data-stage` to each stage section in partial
**File**: `templates/predictions/partials/knockout_stages.html`
**Changes**: Each stage's outer `<details>` (or wrapper `<div>`) gets `data-ko-stage="{{ stage.key }}"` attribute, e.g.:
```html
<div data-ko-stage="{{ stage.key }}">
  <details ...>
    ...
  </details>
</div>
```

#### 3. JS tab switching logic
**File**: `templates/predictions/knockout.html`
**Changes**: Add to the existing IIFE (or as a separate function):
```javascript
let activeKoStage = '{{ stages.0.key }}';

function switchKoStage(key) {
  activeKoStage = key;
  document.querySelectorAll('[data-ko-stage]').forEach(el => {
    el.style.display = el.dataset.koStage === key ? '' : 'none';
  });
  document.querySelectorAll('.ko-tab').forEach(btn => {
    btn.classList.toggle('ko-tab-active', btn.dataset.stage === key);
    btn.classList.toggle('bg-green-600', btn.dataset.stage === key);
    btn.classList.toggle('text-white', btn.dataset.stage === key);
    btn.classList.toggle('bg-gray-100', btn.dataset.stage !== key);
    btn.classList.toggle('text-gray-700', btn.dataset.stage !== key);
  });
}

// Initialize first tab active on page load
document.addEventListener('DOMContentLoaded', () => switchKoStage(activeKoStage));
```

#### 4. Re-apply active tab after HTMX swap
**File**: `templates/predictions/knockout.html`
**Changes**: In the existing `htmx:afterSettle` listener (currently restores details/scroll state), add:
```javascript
switchKoStage(activeKoStage);
```
This re-shows only the active stage after the HTMX innerHTML swap replaces `#ko-bracket`.

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `uv run pytest`
- [x] Lint passes: `uv run ruff check .`

#### Automated QA:
- [ ] Navigate to knockout predictions page — 5 tab buttons appear (R32, R16, QF, SF, Final)
- [ ] Click "QF" tab — only QF matches visible, other stages hidden
- [ ] Enter a QF prediction score and wait 400ms — HTMX fires, bracket refreshes, QF tab still active and QF matches still visible
- [ ] Scroll position maintained after HTMX swap

#### Manual Verification:
- [ ] Tab row scrolls horizontally on small mobile screens
- [ ] Active tab is visually distinct (green background)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 3] knockout phase carousel with CSS tabs`.

---

## Phase 4: Password Recovery

### Overview

Two-step password recovery: user provides email + nickname → if both match a user record → form to set new password → auto-login. No email sending, no tokens, no SMTP required.

### Changes Required:

#### 1. Forms
**File**: `apps/users/forms.py`
**Changes**: Add two new forms:
```python
class PasswordRecoveryForm(forms.Form):
    email = forms.EmailField(label="Email")
    nickname = forms.CharField(max_length=50, label="Apodo")

class SetNewPasswordForm(forms.Form):
    password1 = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return p2
```

#### 2. Views
**File**: `apps/users/views.py`
**Changes**: Add `PasswordRecoveryView` and `SetNewPasswordView`:

```python
class PasswordRecoveryView(FormView):
    template_name = "users/password_recovery.html"
    form_class = PasswordRecoveryForm

    def form_valid(self, form):
        try:
            user = User.objects.get(
                email=form.cleaned_data["email"],
                nickname=form.cleaned_data["nickname"],
            )
        except User.DoesNotExist:
            form.add_error(None, "No encontramos una cuenta con esos datos.")
            return self.form_invalid(form)
        self.request.session["password_recovery_user_id"] = user.pk
        return redirect("set_new_password")


class SetNewPasswordView(FormView):
    template_name = "users/set_password.html"
    form_class = SetNewPasswordForm
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if "password_recovery_user_id" not in request.session:
            return redirect("password_recovery")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = get_object_or_404(User, pk=self.request.session["password_recovery_user_id"])
        user.set_password(form.cleaned_data["password1"])
        user.save()
        del self.request.session["password_recovery_user_id"]
        login(self.request, user)
        return super().form_valid(form)
```

#### 3. URLs
**File**: `apps/users/urls.py`
**Changes**: Add two new paths:
```python
path("password-recovery/", views.PasswordRecoveryView.as_view(), name="password_recovery"),
path("password-recovery/set/", views.SetNewPasswordView.as_view(), name="set_new_password"),
```

#### 4. Templates
**File**: `templates/users/password_recovery.html` *(create)*
**Changes**: Extend `base.html`. Form with email + apodo fields. Error display. Link back to login.

**File**: `templates/users/set_password.html` *(create)*
**Changes**: Extend `base.html`. Form with password1 + password2.

#### 5. Add link to login page
**File**: `templates/users/login.html`
**Changes**: Below the "Registrarse" link, add:
```html
<p class="text-center text-sm text-gray-500 mt-2">
  <a href="{% url 'password_recovery' %}" class="text-green-600 hover:underline">¿Olvidaste tu contraseña?</a>
</p>
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `uv run pytest`
- [x] Lint passes: `uv run ruff check .`

#### Automated QA:
- [ ] Navigate to `/login/` — "¿Olvidaste tu contraseña?" link appears
- [ ] Click link → goes to `/password-recovery/`
- [ ] Submit with wrong email/nickname → error message shown, stays on form
- [ ] Submit with correct email+nickname → redirects to `/password-recovery/set/`
- [ ] Submit new password → redirected to dashboard, user is logged in
- [ ] Navigate directly to `/password-recovery/set/` without session → redirected back to `/password-recovery/`

#### Manual Verification:
- [ ] Password actually changes — can log out and log back in with new password

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 4] password recovery via email + nickname`.

---

## Phase 5: Top Scorer Player Picker

### Overview

Replace the free-text top scorer input with a searchable HTML5 `<datalist>` populated from a new `data/players.json` fixture containing all 48 WC2026 squads. The stored model field remains `player_name CharField`.

### Changes Required:

#### 1. Player data fixture
**File**: `data/players.json` *(create)*
**Changes**: JSON array of player objects, scraped from as.com WC2026 squad lists:
```json
[
  {"name": "Lionel Messi", "team": "ARG", "position": "Delantero"},
  {"name": "Kylian Mbappé", "team": "FRA", "position": "Delantero"},
  ...
]
```
All 48 teams × ~26 players = ~1248 entries. Players should be loaded by web scraping or manual entry during implementation. Focus on forwards + midfielders as they are the most likely top scorers; include all positions for completeness.

*Note for implementor*: Source from https://as.com/futbol/mundial/listas-de-convocados-para-el-mundial-2026-selecciones-y-todos-los-jugadores-que-estaran-en-la-copa-del-mundo-f202605-n-5/ — use the `web-search-researcher` agent to extract player names per team.

#### 2. Load players in PicksView
**File**: `apps/predictions/views.py` (PicksView, lines 211-244)
**Changes**: In `get()`, load `data/players.json` and pass to context:
```python
import json
from pathlib import Path
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Inside PicksView.get():
players_path = DATA_DIR / "players.json"
players = json.loads(players_path.read_text()) if players_path.exists() else []
# Pass to context: ctx["players"] = players
```

#### 3. Update picks template
**File**: `templates/predictions/picks.html`
**Changes**: Replace `<input type="text" name="player_name">` with:
```html
<input
  type="text"
  name="player_name"
  list="players-datalist"
  value="{{ top_scorer_pick.player_name|default:'' }}"
  placeholder="Buscar jugador..."
  class="w-full border ...">
<datalist id="players-datalist">
  {% for player in players %}
    <option value="{{ player.name }}" label="{{ player.team }}">{{ player.name }}</option>
  {% endfor %}
</datalist>
```

### Success Criteria:

#### Automated Verification:
- [x] Tests pass: `uv run pytest`
- [x] Lint passes: `uv run ruff check .`
- [x] Players fixture parseable: `uv run python -c "import json; data=json.load(open('data/players.json')); print(len(data), 'players')"`  → ≥ 500 players

#### Automated QA:
- [ ] Navigate to picks page (after completing group + knockout predictions) — text input now has a datalist dropdown
- [ ] Type "Mes" → dropdown shows Messi and other matching names
- [ ] Select a player → HTMX saves within 400ms (existing mechanism unchanged)
- [ ] Reload page → saved player name persists in input

#### Manual Verification:
- [ ] Datalist shows team code alongside player name (e.g., "ARG" label next to Messi)
- [ ] Works on mobile (native datalist behavior on iOS/Android)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 5] top scorer: searchable player datalist from WC2026 squads`.

---

## Phase 6: Match Schedule Data + Pool Monitoring View

### Overview

Add WC2026 match schedule dates to `wc2026.json`, update the loader to populate `Match.scheduled_at`, and build a new "pool day" view showing all participants' picks for matches on a selected date with a date switcher.

### Changes Required:

#### 1. Data layer: schedule JSON + loader update
**File**: `data/wc2026.json`
**Changes**: Add a `"schedule"` top-level key containing group match dates:
```json
{
  "tournament": { ... },
  "teams": [ ... ],
  "groups": { ... },
  "schedule": [
    {"home": "MEX", "away": "ARG", "date": "2026-06-11T20:00:00-05:00"},
    {"home": "USA", "away": "CAN", "date": "2026-06-11T18:00:00-05:00"},
    ...
  ]
}
```
Group matches are identified by `home` + `away` team `fifa_code`. Knockout match dates are unknown until the bracket resolves — leave them null initially.

*Note for implementor*: Source dates from the official WC2026 schedule. Use `web-search-researcher` to fetch the confirmed match schedule.

Also update `apps/tournaments/management/commands/load_wc2026.py`: after generating group matches, iterate `data.get("schedule", [])` and update `scheduled_at` on matching `Match` records:

```python
from django.utils.dateparse import parse_datetime
for item in data.get("schedule", []):
    dt = parse_datetime(item["date"])
    Match.objects.filter(
        tournament=tournament,
        stage=Match.Stage.GROUP,
        home_team__fifa_code=item["home"],
        away_team__fifa_code=item["away"],
    ).update(scheduled_at=dt)
```

#### 2. View + URL: `PoolDayView`
**File**: `apps/leaderboard/views.py`
**Changes**: Add `PoolDayView` class:

```python
class PoolDayView(LoginRequiredMixin, View):
    def get(self, request, pool_id):
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)
        
        # Determine selected date (default: today or nearest match day)
        date_str = request.GET.get("date")
        if date_str:
            selected_date = datetime.date.fromisoformat(date_str)
        else:
            today = datetime.date.today()
            # Find nearest match date with scheduled matches
            selected_date = today
        
        # Matches on selected date
        matches = Match.objects.filter(
            tournament=pool.tournament,
            scheduled_at__date=selected_date,
        ).select_related("home_team", "away_team").order_by("scheduled_at")
        
        # All submitted memberships
        memberships = PoolMembership.objects.filter(
            pool=pool, predictions_submitted=True
        ).select_related("user")
        
        # For each match, get each member's prediction
        match_data = []
        for match in matches:
            preds = Prediction.objects.filter(
                pool=pool, match=match
            ).select_related("user", "predicted_winner")
            pred_by_user = {p.user_id: p for p in preds}
            participants = [
                {
                    "user": m.user,
                    "prediction": pred_by_user.get(m.user_id),
                }
                for m in memberships
            ]
            match_data.append({"match": match, "participants": participants})
        
        # All available dates (for date switcher)
        available_dates = (
            Match.objects.filter(tournament=pool.tournament, scheduled_at__isnull=False)
            .dates("scheduled_at", "day")
        )
        
        return render(request, "leaderboard/pool_day.html", {
            "pool": pool,
            "selected_date": selected_date,
            "match_data": match_data,
            "available_dates": available_dates,
        })
```

Add route to `apps/leaderboard/urls.py`:
```python
path("pool/<int:pool_id>/day/", PoolDayView.as_view(), name="pool_day"),
```

#### 3. Template: `pool_day.html`
**File**: `templates/leaderboard/pool_day.html` *(create)*
**Changes**: Table layout with:
- Date switcher: prev/next `<a>` links using `?date=YYYY-MM-DD` query params
- Per-match block: flags + team names + time
- Table columns: Usuario | Predicción | Puntos (shows `—` while unscored)
- Empty state: "No hay partidos este día"

#### 4. Dashboard link
**File**: `templates/users/dashboard.html`
**Changes**: Add "Ver partidos del día" link alongside existing "Tabla" button for each pool membership card.

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `uv run pytest`
- [ ] Lint passes: `uv run ruff check .`
- [ ] Loader assigns dates: after running `uv run manage.py load_wc2026`, confirm `Match.objects.filter(scheduled_at__isnull=False).count() > 0`

#### Automated QA:
- [ ] Navigate to `/pool/1/day/` — page loads, shows matches for today (or nearest match day)
- [ ] If matches exist: table shows all submitted members' predictions
- [ ] Click "next day" arrow — URL updates with `?date=`, next day's matches shown
- [ ] Match with `points_awarded` not null — points column shows the value

#### Manual Verification:
- [ ] Date matches are ordered by `scheduled_at` time
- [ ] "Ver partidos del día" link visible on dashboard for each pool

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 6] match schedule data + pool day monitoring view`.

---

## Phase 7: Scoring Configuration Update

### Overview

Update `DEFAULT_SCORING_CONFIG` to user-desired point values and add an admin-editable scoring config note. The per-stage JSON config infrastructure already exists — this phase only changes default values.

### Changes Required:

#### 1. Update DEFAULT_SCORING_CONFIG
**File**: `apps/leaderboard/scoring.py` (lines 11-21)
**Changes**: Update default values to:
```python
DEFAULT_SCORING_CONFIG = {
    "group":       {"exact_score": 3, "correct_result": 5},
    "r32":         {"exact_score": 4, "correct_result": 6, "pens_winner": 1},
    "r16":         {"exact_score": 5, "correct_result": 7, "pens_winner": 1},
    "qf":          {"exact_score": 6, "correct_result": 8, "pens_winner": 1},
    "sf":          {"exact_score": 7, "correct_result": 9, "pens_winner": 1},
    "third_place": {"exact_score": 5, "correct_result": 7, "pens_winner": 1},
    "final":       {"exact_score": 10, "correct_result": 12, "pens_winner": 2},
    "champion":    10,
    "top_scorer":  5,
    # correct_slot added in Phase 8
}
```
*Note*: Exact values to be confirmed with Miguel. The example given was "group winner 5 pts, r32 winner 6 pts" — interpreted as `correct_result` values increasing by phase.

#### 2. FAQ / how-to modal update
**File**: `templates/partials/faq_modal.html`, `templates/partials/howto_modal.html`
**Changes**: Update any hardcoded point values mentioned in the FAQ/how-to text to match the new config.

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `uv run pytest` (existing scoring tests should reflect new values OR be updated)
- [ ] Lint passes: `uv run ruff check .`

#### Automated QA:
- [ ] In a pool with `scoring_config=None`, score a group match exact → 3 points
- [ ] Score a group match with correct result (not exact) → 5 points
- [ ] Score an R32 match with correct result → 6 points

#### Manual Verification:
- [ ] Admin confirms point values match expectations for all 7 stages + champion + top scorer

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 7] update default scoring config point values`.

---

## Phase 8: Bracket Position Bonus Scoring

### Overview

New scoring dimension: `correct_slot` bonus awarded when a user correctly predicted a team to advance to a specific knockout slot, regardless of whether they got the match score right. Stored in new `Prediction.slot_bonus_awarded` field; totaled in leaderboard recalculation.

### Changes Required:

#### 1. Add model field
**File**: `apps/pools/models.py` (Prediction model, after `points_awarded`)
**Changes**:
```python
slot_bonus_awarded = models.IntegerField(null=True, blank=True)
```
*Note*: `null` = not yet computed; `0` = computed, no bonus; positive = bonus awarded.

**Migration**: `uv run manage.py makemigrations pools`

#### 2. Add `correct_slot` to scoring config
**File**: `apps/leaderboard/scoring.py`
**Changes**: Add `correct_slot` key to each knockout stage in `DEFAULT_SCORING_CONFIG`:
```python
"r32": {"exact_score": 4, "correct_result": 6, "pens_winner": 1, "correct_slot": 2},
"r16": {"exact_score": 5, "correct_result": 7, "pens_winner": 1, "correct_slot": 3},
"qf":  {"exact_score": 6, "correct_result": 8, "pens_winner": 1, "correct_slot": 4},
"sf":  {"exact_score": 7, "correct_result": 9, "pens_winner": 1, "correct_slot": 5},
"final":{"exact_score":10,"correct_result":12,"pens_winner": 2, "correct_slot": 6},
```

Add helper `get_slot_bonus(stage, config) -> int`:
```python
def get_slot_bonus(stage, config):
    stage_cfg = config.get(stage, {})
    if isinstance(stage_cfg, dict):
        return stage_cfg.get("correct_slot", 0)
    return 0
```

#### 3. Compute slot bonus in `recalculate_pool_scores`
**File**: `apps/leaderboard/tasks.py` (function `recalculate_pool_scores`)
**Changes**: After computing `prediction.points_awarded`, also compute `slot_bonus_awarded`:

Logic: The slot bonus rewards correctly predicting the WINNER of a match to advance. The predicted winner of this match is the team that advances to the next slot. If `predicted_winner == official_winner`, the user correctly predicted who would occupy this stage's "winner slot".

```python
# After computing points_awarded:
config = get_scoring_config(prediction.pool)
slot_bonus = 0
if match.stage != Match.Stage.GROUP:
    predicted_w = _get_predicted_winner(prediction, match)
    if predicted_w and match.knockout_winner_id and predicted_w == match.knockout_winner_id:
        slot_bonus = get_slot_bonus(match.stage, config)
prediction.slot_bonus_awarded = slot_bonus
prediction.save(update_fields=["points_awarded", "slot_bonus_awarded"])
```

Add helper `_get_predicted_winner(prediction, match) -> int | None`:
```python
def _get_predicted_winner(prediction, match):
    if prediction.predicted_winner_id:
        return prediction.predicted_winner_id
    h, a = prediction.predicted_home_score, prediction.predicted_away_score
    if h is not None and a is not None:
        if h > a:
            return match.home_team_id
        if a > h:
            return match.away_team_id
    return None
```

#### 4. Include slot bonus in leaderboard totals
**File**: `apps/leaderboard/tasks.py` (`_recalculate_leaderboard`)
**Changes**: In the per-user point aggregation, add `slot_bonus_awarded` to the sum:
```python
pred_pts = (
    Prediction.objects.filter(user=m.user, pool=pool)
    .aggregate(
        total=Sum("points_awarded", default=0) + Sum("slot_bonus_awarded", default=0)
    )["total"] or 0
)
```
Or use two separate `aggregate` calls and sum — whichever is cleaner with Django ORM.

#### 5. Display slot bonus in my predictions template
**File**: `templates/leaderboard/my_predictions.html`
**Changes**: Where `points_awarded` badge is shown, also show `slot_bonus_awarded` if non-null and non-zero: e.g. `+{{ pred.slot_bonus_awarded }} bonus` in a separate small chip.

### Success Criteria:

#### Automated Verification:
- [ ] Migration generates cleanly: `uv run manage.py makemigrations pools --check`
- [ ] Apply migration: `uv run manage.py migrate`
- [ ] Tests pass: `uv run pytest`
- [ ] Lint passes: `uv run ruff check .`

#### Automated QA:
- [ ] Score a knockout match where user correctly predicted the winner → `Prediction.slot_bonus_awarded > 0`
- [ ] Score a knockout match where user predicted wrong winner → `Prediction.slot_bonus_awarded == 0`
- [ ] `LeaderboardEntry.total_points` includes the slot bonus
- [ ] My predictions page shows bonus chip for predictions with slot bonus

#### Manual Verification:
- [ ] Bonus values per stage feel reasonable (confirm with Miguel: r32=2, r16=3, qf=4, sf=5, final=6)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 8] bracket position bonus scoring`.

---

## Phase 9: Third-Place Conduct Tiebreaker

### Overview

When a user's group predictions result in a conduct-level tie among third-place teams (i.e., points/GD/GF can't separate the 8th from 9th ranked third-placers), a new view interrupts the knockout flow and asks the user to manually rank the tied teams. A new model `ThirdPlaceTiebreakerPick` stores the user's chosen ranking. If no tie at conduct level, the flow proceeds automatically as before.

### Changes Required:

#### 1. Models + migrations
**Files**: `apps/tournaments/models.py`, `apps/pools/models.py`
**Changes**:
- `TournamentTeam`: add `conduct_score = models.IntegerField(default=0)` (official FIFA conduct score; lower = better)
- `pools/models.py`: add `ThirdPlaceTiebreakerPick` model:
  ```python
  class ThirdPlaceTiebreakerPick(models.Model):
      user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
      pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
      team = models.ForeignKey("tournaments.Team", on_delete=models.CASCADE)
      predicted_rank = models.PositiveIntegerField()  # 1 = best among qualifying thirds
      class Meta:
          unique_together = [("user", "pool", "team")]
  ```
- Run `uv run manage.py makemigrations tournaments pools`

#### 2. Standings + detection
**Files**: `apps/tournaments/standings.py`, `apps/tournaments/services.py`
**Changes**:
- `TeamStanding` dataclass: add `conduct_score: int = 0`
- `_overall_sort`: add `t.conduct_score` step (ascending) before `rankings` in sort key
- `rank_third_place_teams`: same conduct step
- `calculate_group_standings`: populate `standing.conduct_score` from `TournamentTeam.conduct_score`
- `services.py`: add `needs_conduct_tiebreaker(user, pool) -> bool` (checks if 8th/9th ranked thirds tie on points+GD+GF+conduct_score==0) and `get_conduct_tied_thirds(user, pool)` (returns the tied team objects)

#### 3. Flow integration: gate + view + URL
**Files**: `apps/predictions/views.py`, `apps/predictions/urls.py`
**Changes**:
- `KnockoutPredictionsView.dispatch`: after existing group completion check, call `needs_conduct_tiebreaker()`; if True and no picks yet → `redirect("third_place_tiebreaker", pool_id=...)`
- Add `ThirdPlaceTiebreakerView` (GET: show tied teams + existing picks; POST: `update_or_create` picks, redirect to knockout) 
- `urls.py`: `path("third-place-tiebreaker/", ..., name="third_place_tiebreaker")`

#### 4. Template + bracket builder integration
**Files**: `templates/predictions/third_place_tiebreaker.html`, `apps/tournaments/services.py`
**Changes**:
- New template: extend `base.html`; show tied teams with flags (from Phase 2); rank inputs (`<select>` per team, 1–N); submit button → POST
- `build_predicted_knockout_bracket`: before calling `rank_third_place_teams`, check for `ThirdPlaceTiebreakerPick` for this user+pool; if exists, inject those `predicted_rank` values as tiebreaker overrides instead of `conduct_score`

### Success Criteria:

#### Automated Verification:
- [ ] Migrations generate cleanly: `uv run manage.py makemigrations --check`
- [ ] Apply migrations: `uv run manage.py migrate`
- [ ] Tests pass: `uv run pytest`
- [ ] Lint passes: `uv run ruff check .`

#### Automated QA:
- [ ] Simulate group predictions that result in a conduct-level tie at position 8/9 — `needs_conduct_tiebreaker()` returns `True`
- [ ] Navigate to knockout predictions — redirected to tiebreaker page
- [ ] Submit tiebreaker ranking — redirected to knockout bracket
- [ ] Navigate to knockout predictions again — no redirect (tiebreaker picks exist)
- [ ] If no conduct tie exists — knockout view loads directly without redirect

#### Manual Verification:
- [ ] Tiebreaker UI clearly shows which teams are tied and why
- [ ] Tiebreaker picks are reflected in the predicted bracket (tied team ranked 1st appears in bracket)

**Implementation Note**: After this phase, pause for manual confirmation. Commit: `[phase 9] third-place conduct tiebreaker model + user ranking view`.

---

## Appendix

- **Follow-up plans**: 
  - R32 third-place assignment table (495-combination) — currently rank-by-index; proper FIFA table still needed
  - Email-based password reset (if SMTP is added to Railway config in future)
  - Admin scoring config UI (instead of raw JSONField editing in Django admin)
- **Derail notes**:
  - `leaderboard/models.py` and `predictions/models.py` are empty files — all models live in `pools/models.py`. Don't add models to the empty files.
  - `build_predicted_knockout_bracket` in `services.py` is the load-bearing function for bracket display; any change to third-place ranking or slot resolution must go through it.
  - The HTMX state-preservation IIFE in `knockout.html` (lines 40-95) is fragile — modify with care in Phase 3.
- **References**:
  - Research: `thoughts/miguel/research/2026-05-28-feature-batch-flags-knockout-monitoring-scoring-auth-branding.md`
  - Prior plan: `thoughts/miguel/plans/2026-05-11-quiniela-v2-implementation.md`
