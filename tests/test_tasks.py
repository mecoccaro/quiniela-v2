from unittest.mock import patch

import pytest

from apps.leaderboard.tasks import _recalculate_leaderboard, recalculate_pool_scores, score_final_picks
from apps.pools.models import (
    LeaderboardEntry,
    Pool,
    PoolChampionPick,
    PoolMembership,
    PoolTopScorerPick,
    Prediction,
)
from apps.tournaments.models import Match, Team, Tournament, TournamentTeam
from apps.tournaments.services import BracketSlot
from apps.users.models import User


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="Task Cup", slug="task-cup")


@pytest.fixture
def teams(db):
    return [Team.objects.create(name=f"TT{c}", fifa_code=f"T{c}") for c in "AB"]


@pytest.fixture
def pool(db, tournament):
    return Pool.objects.create(name="Task Pool", tournament=tournament)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="task@example.com", nickname="taskuser",
        password="TestPass123!", first_name="T", last_name="A",
    )


@pytest.fixture
def membership(db, pool, user):
    return PoolMembership.objects.create(pool=pool, user=user)


@pytest.fixture
def group_match(db, tournament, teams):
    ta, tb = teams
    TournamentTeam.objects.create(tournament=tournament, team=ta, group_letter="A", fifa_ranking=1)
    TournamentTeam.objects.create(tournament=tournament, team=tb, group_letter="A", fifa_ranking=2)
    return Match.objects.create(
        tournament=tournament, stage=Match.Stage.GROUP, group_letter="A",
        home_team=ta, away_team=tb,
    )


@pytest.mark.django_db
def test_recalculate_sets_points_awarded(pool, user, membership, group_match):
    Prediction.objects.create(
        user=user, pool=pool, match=group_match,
        predicted_home_score=2, predicted_away_score=1,
    )
    group_match.home_score = 2
    group_match.away_score = 1
    group_match.status = Match.Status.COMPLETED
    group_match.save()

    pred = Prediction.objects.get(user=user, pool=pool, match=group_match)
    assert pred.points_awarded == 7  # exact score: resultado=3 + goals_a=1 + goals_b=1 + bonus=2


@pytest.mark.django_db
def test_recalculate_creates_leaderboard_entry(pool, user, membership, group_match):
    Prediction.objects.create(
        user=user, pool=pool, match=group_match,
        predicted_home_score=2, predicted_away_score=0,
    )
    group_match.home_score = 3
    group_match.away_score = 0
    group_match.status = Match.Status.COMPLETED
    group_match.save()

    entry = LeaderboardEntry.objects.get(pool=pool, user=user)
    assert entry.total_points == 4  # correct result: resultado=3 + goals_b=1 (away=0 matches)
    assert entry.rank == 1


@pytest.mark.django_db
def test_recalculate_direct_call(pool, user, membership, group_match):
    """Call the task directly (bypassing signal) via .apply() to test task logic."""
    Prediction.objects.create(
        user=user, pool=pool, match=group_match,
        predicted_home_score=1, predicted_away_score=2,
    )
    group_match.home_score = 0
    group_match.away_score = 3
    group_match.status = Match.Status.COMPLETED
    group_match.save(update_fields=["home_score", "away_score", "status"])

    recalculate_pool_scores.apply(args=[group_match.pk])

    pred = Prediction.objects.get(user=user, pool=pool, match=group_match)
    assert pred.points_awarded == 3  # correct result (away win): resultado=3, no individual goals match


@pytest.mark.django_db
def test_recalculate_dense_ranking(pool, tournament, group_match):
    user_a = User.objects.create_user(
        email="a@example.com", nickname="auser", password="TestPass123!", first_name="A", last_name="A"
    )
    user_b = User.objects.create_user(
        email="b@example.com", nickname="buser", password="TestPass123!", first_name="B", last_name="B"
    )
    PoolMembership.objects.create(pool=pool, user=user_a)
    PoolMembership.objects.create(pool=pool, user=user_b)

    # user_a: exact score (7 pts), user_b: wrong (0 pts)
    Prediction.objects.create(user=user_a, pool=pool, match=group_match, predicted_home_score=2, predicted_away_score=1)
    Prediction.objects.create(user=user_b, pool=pool, match=group_match, predicted_home_score=0, predicted_away_score=3)

    group_match.home_score = 2
    group_match.away_score = 1
    group_match.status = Match.Status.COMPLETED
    group_match.save()

    entry_a = LeaderboardEntry.objects.get(pool=pool, user=user_a)
    entry_b = LeaderboardEntry.objects.get(pool=pool, user=user_b)
    assert entry_a.rank == 1
    assert entry_b.rank == 2


@pytest.mark.django_db
def test_score_final_picks_champion(pool, user, membership, teams, tournament):
    ta, tb = teams
    PoolChampionPick.objects.create(user=user, pool=pool, team=ta)

    score_final_picks.apply(args=[tournament.pk, ta.pk, "Messi"])

    pick = PoolChampionPick.objects.get(user=user, pool=pool)
    assert pick.points_awarded == 30


@pytest.mark.django_db
def test_score_final_picks_top_scorer_case_insensitive(pool, user, membership, tournament):
    PoolTopScorerPick.objects.create(user=user, pool=pool, player_name="messi")

    score_final_picks.apply(args=[tournament.pk, 999, "Messi"])

    pick = PoolTopScorerPick.objects.get(user=user, pool=pool)
    assert pick.points_awarded == 30


@pytest.mark.django_db
def test_score_final_picks_wrong_top_scorer(pool, user, membership, tournament):
    PoolTopScorerPick.objects.create(user=user, pool=pool, player_name="Ronaldo")

    score_final_picks.apply(args=[tournament.pk, 999, "Messi"])

    pick = PoolTopScorerPick.objects.get(user=user, pool=pool)
    assert pick.points_awarded == 0


@pytest.mark.django_db
def test_advancement_bonus_r16(pool, user, membership, tournament):
    """
    Advancement bonus: user correctly predicts 2 of the 2 r16 teams.
    r16 pts_per_team = 4, so expected advancement_bonus_total = 2 * 4 = 8.
    """
    # Create 4 teams that will appear in r16
    team_x = Team.objects.create(name="TeamX", fifa_code="TXX")
    team_y = Team.objects.create(name="TeamY", fifa_code="TYY")
    team_z = Team.objects.create(name="TeamZ", fifa_code="TZZ")
    team_w = Team.objects.create(name="TeamW", fifa_code="TWW")

    # Create one real r16 match with team_x vs team_y (both teams assigned = in this round)
    Match.objects.create(
        tournament=tournament,
        stage=Match.Stage.R16,
        home_team=team_x,
        away_team=team_y,
        bracket_slot="R16_TEST_1",
        status=Match.Status.SCHEDULED,
    )

    # Build a fake bracket where the user predicted team_x and team_y in r16
    # (matching the real teams → 2 correct), and team_z/team_w elsewhere (not in real r16)
    fake_r16_slots = [
        BracketSlot(slot_key="R16_TEST_1", home_team=team_x, away_team=team_y, match=None, prediction=None),
        BracketSlot(slot_key="R16_TEST_2", home_team=team_z, away_team=team_w, match=None, prediction=None),
    ]
    fake_bracket = {"r16": fake_r16_slots}

    with patch("apps.tournaments.services.build_predicted_knockout_bracket", return_value=fake_bracket):
        _recalculate_leaderboard(pool.pk)

    entry = LeaderboardEntry.objects.get(pool=pool, user=user)
    # r16 pts_per_team = 4 (DEFAULT_SCORING_CONFIG), 2 correct teams → 8 pts
    assert entry.advancement_bonus_total == 8


@pytest.mark.django_db
def test_advancement_bonus_partial_match(pool, user, membership, tournament):
    """
    Advancement bonus: user correctly predicts only 1 of the 2 r16 teams.
    Expected advancement_bonus_total = 1 * 4 = 4.
    """
    team_x = Team.objects.create(name="TeamX2", fifa_code="TX2")
    team_y = Team.objects.create(name="TeamY2", fifa_code="TY2")
    team_wrong = Team.objects.create(name="WrongTeam", fifa_code="WRG")

    # Real r16 match has team_x and team_y
    Match.objects.create(
        tournament=tournament,
        stage=Match.Stage.R16,
        home_team=team_x,
        away_team=team_y,
        bracket_slot="R16_P_1",
        status=Match.Status.SCHEDULED,
    )

    # User predicted team_x (correct) and team_wrong (incorrect)
    fake_r16_slots = [
        BracketSlot(slot_key="R16_P_1", home_team=team_x, away_team=team_wrong, match=None, prediction=None),
    ]
    fake_bracket = {"r16": fake_r16_slots}

    with patch("apps.tournaments.services.build_predicted_knockout_bracket", return_value=fake_bracket):
        _recalculate_leaderboard(pool.pk)

    entry = LeaderboardEntry.objects.get(pool=pool, user=user)
    assert entry.advancement_bonus_total == 4  # 1 correct team × 4 pts


@pytest.mark.django_db
def test_advancement_bonus_empty_when_no_real_teams(pool, user, membership, tournament):
    """
    Advancement bonus: if no r16 matches have teams assigned yet, bonus is 0.
    """
    team_x = Team.objects.create(name="TeamX3", fifa_code="TX3")
    team_y = Team.objects.create(name="TeamY3", fifa_code="TY3")

    # r16 match exists but has no home/away teams assigned (TBD)
    Match.objects.create(
        tournament=tournament,
        stage=Match.Stage.R16,
        home_team=None,
        away_team=None,
        bracket_slot="R16_EMPTY_1",
        status=Match.Status.SCHEDULED,
    )

    fake_r16_slots = [
        BracketSlot(slot_key="R16_EMPTY_1", home_team=team_x, away_team=team_y, match=None, prediction=None),
    ]
    fake_bracket = {"r16": fake_r16_slots}

    with patch("apps.tournaments.services.build_predicted_knockout_bracket", return_value=fake_bracket):
        _recalculate_leaderboard(pool.pk)

    entry = LeaderboardEntry.objects.get(pool=pool, user=user)
    assert entry.advancement_bonus_total == 0  # no real teams → skipped
