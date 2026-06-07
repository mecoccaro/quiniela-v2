from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone


@shared_task
def recalculate_pool_scores(match_id: int) -> None:
    """Recalculate points for all predictions of this match and update leaderboard entries."""
    from apps.leaderboard.scoring import get_scoring_config, score_prediction
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

        if match.stage == Match.Stage.GROUP:
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
            slot_bonus = 0
        else:
            points, slot_bonus = _score_knockout_prediction(prediction, match, config)

        prediction.points_awarded = points
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


def _compute_advancement_bonus(user, pool, config) -> int:
    from apps.tournaments.models import Match
    from apps.tournaments.services import build_predicted_knockout_bracket

    adv_cfg = config.get("advancement", {})
    if not adv_cfg:
        return 0

    tournament = pool.tournament
    bracket = build_predicted_knockout_bracket(user, pool)
    total = 0

    for stage, pts_per_team in adv_cfg.items():
        # Real teams in this round (from completed matches with both teams assigned)
        stage_matches = Match.objects.filter(
            tournament=tournament,
            stage=stage,
            home_team__isnull=False,
            away_team__isnull=False,
        )
        real_ids: set[int] = set()
        for m in stage_matches:
            if m.home_team_id is not None:
                real_ids.add(m.home_team_id)
            if m.away_team_id is not None:
                real_ids.add(m.away_team_id)

        if not real_ids:
            continue  # round hasn't started yet

        # Predicted teams for this round
        predicted_ids: set[int] = set()
        for slot in bracket.get(stage, []):
            if slot.home_team:
                predicted_ids.add(slot.home_team.pk)
            if slot.away_team:
                predicted_ids.add(slot.away_team.pk)

        correct = predicted_ids & real_ids
        total += len(correct) * pts_per_team

    return total


def _compute_group_classification_bonus(user, pool) -> int:
    from apps.leaderboard.scoring import get_scoring_config
    from apps.tournaments.models import Match, TournamentTeam
    from apps.tournaments.services import get_actual_group_standings, get_predicted_group_standings
    from apps.tournaments.standings import rank_third_place_teams

    tournament = pool.tournament
    config = get_scoring_config(pool)
    cls_cfg = config.get("group_classification", {})
    if not cls_cfg:
        return 0

    # Guard: only compute once all group matches are complete
    incomplete = Match.objects.filter(
        tournament=tournament,
        stage=Match.Stage.GROUP,
    ).exclude(status=Match.Status.COMPLETED).exists()
    if incomplete:
        return 0

    # Get all group letters from the tournament
    group_letters = list(
        TournamentTeam.objects.filter(tournament=tournament)
        .values_list("group_letter", flat=True)
        .distinct()
    )

    total = 0
    predicted_thirds: dict[str, int] = {}  # group_letter → predicted 3rd team_id
    actual_thirds: dict[str, int] = {}     # group_letter → actual 3rd team_id
    all_actual_third_standings = []

    for letter in group_letters:
        predicted = get_predicted_group_standings(user, pool, letter)
        actual = get_actual_group_standings(tournament, letter)
        if not predicted or not actual:
            continue

        pred_map = {s.position: s.team_id for s in predicted}
        act_map = {s.position: s.team_id for s in actual}

        if pred_map.get(1) == act_map.get(1):
            total += cls_cfg.get("first_place", 0)
        if pred_map.get(2) == act_map.get(2):
            total += cls_cfg.get("second_place", 0)

        if 3 in pred_map:
            predicted_thirds[letter] = pred_map[3]
        if 3 in act_map:
            actual_thirds[letter] = act_map[3]
            # Collect the actual 3rd-place TeamStanding for ranking
            for s in actual:
                if s.position == 3:
                    all_actual_third_standings.append(s)
                    break

    # 3rd place: only score if the predicted team is among the best 8 actual third-placers
    rankings = {
        tt.team_id: tt.fifa_ranking
        for tt in TournamentTeam.objects.filter(tournament=tournament)
        if tt.fifa_ranking is not None
    }
    ranked_thirds = rank_third_place_teams(all_actual_third_standings, rankings)
    top8_actual_thirds = {s.team_id for s in ranked_thirds[:8]}

    third_pts = cls_cfg.get("third_place", 0)
    for _letter, pred_3rd in predicted_thirds.items():
        if pred_3rd in top8_actual_thirds:
            total += third_pts

    return total


def _score_knockout_prediction(prediction, match, config) -> tuple[int, int]:
    """Score a knockout prediction directly. No bracket-slot gating in v4."""
    from apps.leaderboard.scoring import score_prediction

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
    return points, 0  # slot_bonus always 0 in v4


def _recalculate_leaderboard(pool_id: int) -> None:
    from apps.leaderboard.scoring import get_scoring_config  # noqa: PLC0415
    from apps.pools.models import (  # noqa: PLC0415
        LeaderboardEntry,
        Pool,
        PoolChampionPick,
        PoolTopScorerPick,
        Prediction,
    )

    with transaction.atomic():
        pool = Pool.objects.get(pk=pool_id)
        config = get_scoring_config(pool)

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
            adv_bonus = _compute_advancement_bonus(user, pool, config)
            cls_bonus = _compute_group_classification_bonus(user, pool)

            LeaderboardEntry.objects.update_or_create(
                pool=pool,
                user=user,
                defaults={
                    "total_points": pred_pts + champ_pts + scorer_pts + adv_bonus + cls_bonus,
                    "advancement_bonus_total": adv_bonus,
                    "group_classification_bonus": cls_bonus,
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
