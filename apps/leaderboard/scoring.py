from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.pools.models import Pool

DEFAULT_SCORING_CONFIG: dict[str, int] = {
    "exact_score": 3,
    "correct_result": 1,
    "pens_winner": 1,
    "champion": 5,
    "top_scorer": 3,
}


def get_scoring_config(pool: Pool) -> dict[str, int]:
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


def score_prediction(
    predicted_home: int,
    predicted_away: int,
    official_home: int,
    official_away: int,
    stage: str,
    predicted_winner_id: int | None,
    official_knockout_winner_id: int | None,
    config: dict[str, int],
) -> int:
    """Return points awarded for one prediction against the official result."""
    points = 0

    if predicted_home == official_home and predicted_away == official_away:
        points += config.get("exact_score", DEFAULT_SCORING_CONFIG["exact_score"])
    elif _outcome(predicted_home, predicted_away) == _outcome(official_home, official_away):
        points += config.get("correct_result", DEFAULT_SCORING_CONFIG["correct_result"])

    if (
        stage != "group"
        and predicted_winner_id is not None
        and official_knockout_winner_id is not None
        and predicted_winner_id == official_knockout_winner_id
    ):
        points += config.get("pens_winner", DEFAULT_SCORING_CONFIG["pens_winner"])

    return points
