from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.pools.models import Pool

# Per-stage scoring config (new format).
# Each stage key maps to a dict with exact_score, correct_result, and (for knockout) pens_winner.
# champion and top_scorer remain top-level keys.
DEFAULT_SCORING_CONFIG: dict = {
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


def _stage_values(stage: str, config: dict) -> tuple[int, int, int]:
    """Return (exact_pts, result_pts, pens_pts) for the given stage and config.

    Supports two config formats:
    - Per-stage (new): config[stage] is a dict with exact_score / correct_result / pens_winner
    - Flat (legacy):   config has exact_score / correct_result / pens_winner at top level
    """
    stage_config = config.get(stage)
    if isinstance(stage_config, dict):
        exact_pts = stage_config.get("exact_score", 3)
        result_pts = stage_config.get("correct_result", 1)
        pens_pts = stage_config.get("pens_winner", 1)
    else:
        # Legacy flat format
        exact_pts = config.get("exact_score", 3)
        result_pts = config.get("correct_result", 1)
        pens_pts = config.get("pens_winner", 1)
    return exact_pts, result_pts, pens_pts


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
    """Return points awarded for one prediction against the official result."""
    exact_pts, result_pts, pens_pts = _stage_values(stage, config)

    points = 0
    if predicted_home == official_home and predicted_away == official_away:
        points += exact_pts
    elif _outcome(predicted_home, predicted_away) == _outcome(official_home, official_away):
        points += result_pts

    if (
        stage != "group"
        and predicted_winner_id is not None
        and official_knockout_winner_id is not None
        and predicted_winner_id == official_knockout_winner_id
    ):
        points += pens_pts

    return points
