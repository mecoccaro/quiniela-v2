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
) -> int:
    """Return points for one prediction. All v4 components are additive.

    For knockout clasificado, the predicted winner is taken from
    ``predicted_winner_id`` when set, otherwise inferred from a decisive
    predicted scoreline (same rule the bracket builder uses). This mirrors the
    UX: a winner pick is only stored explicitly when the user predicts a draw.
    """
    s = _v4_stage_values(stage, config)
    points = 0

    # Resultado: outcome direction (home/draw/away)
    if _outcome(predicted_home, predicted_away) == _outcome(official_home, official_away):
        points += s.get("correct_resultado", 0)

    # Individual goal correctness
    if predicted_home == official_home:
        points += s.get("correct_goals_team_a", 0)
    if predicted_away == official_away:
        points += s.get("correct_goals_team_b", 0)

    # Bonus: additive when both goals exact
    if predicted_home == official_home and predicted_away == official_away:
        points += s.get("bonus_exact_score", 0)

    # Clasificado: knockout only. Use the explicit winner pick if present,
    # otherwise infer it from a decisive predicted scoreline.
    effective_winner_id = predicted_winner_id
    if effective_winner_id is None and predicted_home != predicted_away:
        effective_winner_id = home_team_id if predicted_home > predicted_away else away_team_id

    if (
        stage != "group"
        and effective_winner_id is not None
        and official_knockout_winner_id is not None
        and effective_winner_id == official_knockout_winner_id
    ):
        points += s.get("correct_clasificado", 0)

    return points
