from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


@shared_task
def recalculate_pool_scores(match_id: int) -> None:
    """Recalculate points for all predictions of this match and update leaderboard entries."""
    from apps.leaderboard.scoring import get_scoring_config, get_slot_bonus, score_prediction
    from apps.pools.models import Prediction
    from apps.tournaments.models import Match

    match = Match.objects.select_related("tournament").get(pk=match_id)
    if match.home_score is None or match.away_score is None:
        return

    predictions = Prediction.objects.filter(match=match).select_related(
        "pool__tournament", "predicted_winner"
    )

    for prediction in predictions:
        config = get_scoring_config(prediction.pool)
        points = score_prediction(
            predicted_home=prediction.predicted_home_score,
            predicted_away=prediction.predicted_away_score,
            official_home=match.home_score,
            official_away=match.away_score,
            stage=match.stage,
            predicted_winner_id=prediction.predicted_winner_id,
            official_knockout_winner_id=match.knockout_winner_id,
            config=config,
        )
        prediction.points_awarded = points
        slot_bonus = 0
        if match.stage != Match.Stage.GROUP:
            predicted_w = _get_predicted_winner(prediction, match)
            if predicted_w and match.knockout_winner_id and predicted_w == match.knockout_winner_id:
                slot_bonus = get_slot_bonus(match.stage, config)
        prediction.slot_bonus_awarded = slot_bonus
        prediction.save(update_fields=["points_awarded", "slot_bonus_awarded"])

    affected_pool_ids = list(predictions.values_list("pool_id", flat=True).distinct())
    for pool_id in affected_pool_ids:
        _recalculate_leaderboard(pool_id)


@shared_task
def score_final_picks(tournament_id: int, official_champion_id: int, official_top_scorer_name: str) -> None:
    """Score champion and top scorer picks for all pools in a tournament, then update leaderboards."""
    from apps.leaderboard.scoring import get_scoring_config
    from apps.pools.models import Pool, PoolChampionPick, PoolTopScorerPick

    pools = Pool.objects.filter(tournament_id=tournament_id).select_related("tournament")

    for pool in pools:
        config = get_scoring_config(pool)
        champion_pts = config.get("champion", 5)
        top_scorer_pts = config.get("top_scorer", 3)

        PoolChampionPick.objects.filter(pool=pool, team_id=official_champion_id).update(
            points_awarded=champion_pts
        )
        PoolChampionPick.objects.filter(pool=pool).exclude(team_id=official_champion_id).update(
            points_awarded=0
        )

        normalized = official_top_scorer_name.strip().lower()
        for pick in PoolTopScorerPick.objects.filter(pool=pool):
            pick.points_awarded = top_scorer_pts if pick.player_name.strip().lower() == normalized else 0
            pick.save(update_fields=["points_awarded"])

        _recalculate_leaderboard(pool.pk)


def _get_predicted_winner(prediction, match) -> int | None:
    """Return the predicted winner team ID for a knockout match prediction.

    Prefers explicit predicted_winner (draw+pens case); falls back to deriving
    from the predicted scoreline.
    """
    if prediction.predicted_winner_id:
        return prediction.predicted_winner_id
    h, a = prediction.predicted_home_score, prediction.predicted_away_score
    if h is not None and a is not None:
        if h > a:
            return match.home_team_id
        if a > h:
            return match.away_team_id
    return None


def _recalculate_leaderboard(pool_id: int) -> None:
    from apps.pools.models import (  # noqa: PLC0415
        LeaderboardEntry,
        Pool,
        PoolChampionPick,
        PoolTopScorerPick,
        Prediction,
    )

    with transaction.atomic():
        pool = Pool.objects.get(pk=pool_id)

        for membership in pool.memberships.select_related("user"):
            user = membership.user

            pred_agg = Prediction.objects.filter(pool=pool, user=user).aggregate(
                pts=Sum("points_awarded"),
                bonus=Sum("slot_bonus_awarded"),
            )
            pred_pts = (pred_agg["pts"] or 0) + (pred_agg["bonus"] or 0)
            champ_pts = (
                PoolChampionPick.objects.filter(pool=pool, user=user).aggregate(t=Sum("points_awarded"))["t"] or 0
            )
            scorer_pts = (
                PoolTopScorerPick.objects.filter(pool=pool, user=user).aggregate(t=Sum("points_awarded"))["t"] or 0
            )

            LeaderboardEntry.objects.update_or_create(
                pool=pool,
                user=user,
                defaults={
                    "total_points": pred_pts + champ_pts + scorer_pts,
                    "last_calculated_at": timezone.now(),
                },
            )

        entries = list(LeaderboardEntry.objects.filter(pool=pool).order_by("-total_points"))
        rank = 1
        for i, entry in enumerate(entries):
            if i > 0 and entry.total_points < entries[i - 1].total_points:
                rank = i + 1
            entry.previous_rank = entry.rank if entry.rank != 0 else None
            entry.rank = rank
            entry.save(update_fields=["rank", "previous_rank"])
