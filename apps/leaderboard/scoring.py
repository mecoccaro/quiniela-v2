from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.pools.models import Pool

# v4 additive scoring config.
# Each stage key maps to a dict with correct_resultado, correct_goals_team_a/b,
# bonus_exact_score, and (for knockout stages) correct_clasificado.
# advancement and group_classification are bonus categories computed at leaderboard level.
# champion and top_scorer remain top-level keys.
DEFAULT_SCORING_CONFIG: dict = {
    "group": {
        "correct_resultado": 3,
        "correct_goals_team_a": 1,
        "correct_goals_team_b": 1,
        "bonus_exact_score": 2,
    },
    "r32": {
        "correct_resultado": 6,
        "correct_clasificado": 2,
        "correct_goals_team_a": 2,
        "correct_goals_team_b": 2,
        "bonus_exact_score": 4,
    },
    "r16": {
        "correct_resultado": 12,
        "correct_clasificado": 3,
        "correct_goals_team_a": 3,
        "correct_goals_team_b": 3,
        "bonus_exact_score": 6,
    },
    "qf": {
        "correct_resultado": 18,
        "correct_clasificado": 4,
        "correct_goals_team_a": 4,
        "correct_goals_team_b": 4,
        "bonus_exact_score": 8,
    },
    "sf": {
        "correct_resultado": 24,
        "correct_clasificado": 5,
        "correct_goals_team_a": 5,
        "correct_goals_team_b": 5,
        "bonus_exact_score": 10,
    },
    "third_place": {
        "correct_resultado": 12,
        "correct_clasificado": 3,
        "correct_goals_team_a": 3,
        "correct_goals_team_b": 3,
        "bonus_exact_score": 6,
    },
    "final": {
        "correct_resultado": 30,
        "correct_clasificado": 6,
        "correct_goals_team_a": 6,
        "correct_goals_team_b": 6,
        "bonus_exact_score": 12,
    },
    "advancement": {
        "r16": 4,
        "qf": 8,
        "sf": 16,
        "final": 32,
    },
    "group_classification": {
        "first_place": 6,
        "second_place": 6,
        "third_place": 4,
    },
    "champion": 30,
    "top_scorer": 30,
}


def get_scoring_config(pool: Pool) -> dict:
    """Return the effective scoring config: pool override → tournament config → built-in default."""
    if pool.scoring_config:
        return pool.scoring_config
    if pool.tournament.scoring_config:
        return pool.tournament.scoring_config
    return DEFAULT_SCORING_CONFIG


def _outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def _v4_stage_values(stage: str, config: dict) -> dict:
    """Return v4 scoring components for the stage. Falls back to legacy flat-format keys."""
    stage_cfg = config.get(stage)
    if isinstance(stage_cfg, dict) and "correct_resultado" in stage_cfg:
        return stage_cfg  # v4 format
    # Legacy flat format — map old keys to v4 equivalents
    flat = stage_cfg if isinstance(stage_cfg, dict) else config
    return {
        "correct_resultado": flat.get("correct_result", 0),
        "correct_goals_team_a": 0,
        "correct_goals_team_b": 0,
        "bonus_exact_score": flat.get("exact_score", 0),
        "correct_clasificado": flat.get("pens_winner", 0),
    }


def _predicted_winner_team(
    predicted_home: int,
    predicted_away: int,
    predicted_home_team_id: int | None,
    predicted_away_team_id: int | None,
    predicted_winner_id: int | None,
) -> int | None:
    """Which team the user predicted to advance: decisive → score side, draw → explicit pick."""
    if predicted_home > predicted_away:
        return predicted_home_team_id
    if predicted_away > predicted_home:
        return predicted_away_team_id
    return predicted_winner_id  # draw → goes to penalties → explicit winner pick


def score_prediction(
    predicted_home: int,
    predicted_away: int,
    official_home: int,
    official_away: int,
    stage: str,
    predicted_winner_id: int | None,
    official_knockout_winner_id: int | None,
    config: dict,
    home_team_id: int | None = None,
    away_team_id: int | None = None,
    predicted_home_team_id: int | None = None,
    predicted_away_team_id: int | None = None,
) -> int:
    """Return points for one prediction.

    Group stage is purely additive on the scoreline. Knockout scoring is gated by
    how well the predicted *teams* of the bracket slot match the real teams
    (resultado/ganador are evaluated per team, not per side):

    - Caso A — both predicted teams correct on their side: goals (both) + resultado + clasificado + bonus
    - Caso B — exactly one predicted team correct on its side: goals (that side only) + resultado + clasificado
    - Caso C — a predicted team is present but neither on its correct side: clasificado only
    - Caso D — no predicted team is in the real match: 0
    """
    s = _v4_stage_values(stage, config)

    if stage == "group":
        return _score_group(predicted_home, predicted_away, official_home, official_away, s)

    return _score_knockout(
        predicted_home,
        predicted_away,
        official_home,
        official_away,
        s,
        predicted_winner_id,
        official_knockout_winner_id,
        home_team_id,
        away_team_id,
        predicted_home_team_id,
        predicted_away_team_id,
    )


def _score_group(
    predicted_home: int,
    predicted_away: int,
    official_home: int,
    official_away: int,
    s: dict,
) -> int:
    """Additive group scoring: resultado direction + per-side goals + exact bonus."""
    points = 0
    if _outcome(predicted_home, predicted_away) == _outcome(official_home, official_away):
        points += s.get("correct_resultado", 0)
    if predicted_home == official_home:
        points += s.get("correct_goals_team_a", 0)
    if predicted_away == official_away:
        points += s.get("correct_goals_team_b", 0)
    if predicted_home == official_home and predicted_away == official_away:
        points += s.get("bonus_exact_score", 0)
    return points


def _score_knockout(
    predicted_home: int,
    predicted_away: int,
    official_home: int,
    official_away: int,
    s: dict,
    predicted_winner_id: int | None,
    official_knockout_winner_id: int | None,
    home_team_id: int | None,
    away_team_id: int | None,
    predicted_home_team_id: int | None,
    predicted_away_team_id: int | None,
) -> int:
    """Team-aware knockout scoring. See score_prediction for the tier rules."""
    predicted_teams = {t for t in (predicted_home_team_id, predicted_away_team_id) if t is not None}
    real_teams = {t for t in (home_team_id, away_team_id) if t is not None}

    # Tier 0: none of the predicted teams are actually in this match.
    if not predicted_teams or not (predicted_teams & real_teams):
        return 0

    exact_home = predicted_home_team_id is not None and predicted_home_team_id == home_team_id
    exact_away = predicted_away_team_id is not None and predicted_away_team_id == away_team_id

    if exact_home and exact_away:
        tier = 1
    elif exact_home or exact_away:
        tier = 2
    else:
        tier = 3

    points = 0

    # Ganador / clasificado — Casos A, B and C (any predicted team present).
    predicted_winner_team = _predicted_winner_team(
        predicted_home, predicted_away, predicted_home_team_id, predicted_away_team_id, predicted_winner_id
    )
    if (
        official_knockout_winner_id is not None
        and predicted_winner_team is not None
        and predicted_winner_team == official_knockout_winner_id
    ):
        points += s.get("correct_clasificado", 0)

    # Resultado — Casos A and B only. Per-team outcome type match (winner team, or both draw→pens).
    if tier in (1, 2) and _resultado_matches(
        predicted_home,
        predicted_away,
        official_home,
        official_away,
        predicted_home_team_id,
        predicted_away_team_id,
        home_team_id,
        away_team_id,
    ):
        points += s.get("correct_resultado", 0)

    # Goals — Caso A both sides; Caso B only the correctly-placed team's side.
    if tier == 1:
        if predicted_home == official_home:
            points += s.get("correct_goals_team_a", 0)
        if predicted_away == official_away:
            points += s.get("correct_goals_team_b", 0)
    elif tier == 2:
        if exact_home and predicted_home == official_home:
            points += s.get("correct_goals_team_a", 0)
        if exact_away and predicted_away == official_away:
            points += s.get("correct_goals_team_b", 0)

    # Bonus — Caso A only: exact scoreline with both teams correctly placed.
    if tier == 1 and predicted_home == official_home and predicted_away == official_away:
        points += s.get("bonus_exact_score", 0)

    return points


def _resultado_matches(
    predicted_home: int,
    predicted_away: int,
    official_home: int,
    official_away: int,
    predicted_home_team_id: int | None,
    predicted_away_team_id: int | None,
    home_team_id: int | None,
    away_team_id: int | None,
) -> bool:
    """True when the predicted result type matches the real one, evaluated per team.

    Both went to penalties (draw scoreline) → match. Both decisive → match only when
    the predicted winning team equals the real winning team (regardless of which side).
    """
    predicted_draw = predicted_home == predicted_away
    real_draw = official_home == official_away
    if predicted_draw != real_draw:
        return False
    if predicted_draw:
        return True  # both went to penalties
    predicted_winner = predicted_home_team_id if predicted_home > predicted_away else predicted_away_team_id
    real_winner = home_team_id if official_home > official_away else away_team_id
    return predicted_winner is not None and predicted_winner == real_winner
