import pytest

from apps.pools.models import Pool, Prediction
from apps.tournaments.models import Match, Team, Tournament, TournamentTeam
from apps.tournaments.services import get_predicted_group_standings
from apps.users.models import User


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="Test Cup", slug="test-cup")


@pytest.fixture
def group_a_teams(db, tournament):
    teams = [
        Team.objects.create(name=f"Team {c}", fifa_code=f"T{c}") for c in "ABCD"
    ]
    for i, team in enumerate(teams, start=1):
        TournamentTeam.objects.create(
            tournament=tournament, team=team, group_letter="A", fifa_ranking=i
        )
    return teams


@pytest.fixture
def group_a_matches(db, tournament, group_a_teams):
    ta, tb, tc, td = group_a_teams
    pairs = [(ta, tb), (ta, tc), (ta, td), (tb, tc), (tb, td), (tc, td)]
    return [
        Match.objects.create(
            tournament=tournament,
            stage=Match.Stage.GROUP,
            group_letter="A",
            home_team=home,
            away_team=away,
        )
        for home, away in pairs
    ]


@pytest.fixture
def pool(db, tournament):
    return Pool.objects.create(name="Test Pool", tournament=tournament)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com", nickname="tester",
        password="pass", first_name="T", last_name="U",
    )


@pytest.mark.django_db
def test_get_predicted_group_standings_ordering(user, pool, group_a_teams, group_a_matches):
    ta, tb, tc, td = group_a_teams
    scores = {
        (ta, tb): (3, 0), (ta, tc): (2, 1), (ta, td): (1, 0),
        (tb, tc): (1, 0), (tb, td): (1, 0),
        (tc, td): (1, 0),
    }
    for match in group_a_matches:
        home, away = match.home_team, match.away_team
        hs, as_ = scores[(home, away)]
        Prediction.objects.create(
            user=user, pool=pool, match=match,
            predicted_home_score=hs, predicted_away_score=as_,
        )

    result = get_predicted_group_standings(user, pool, "A")
    assert len(result) == 4
    assert result[0].team_id == ta.pk
    assert result[1].team_id == tb.pk
    assert result[2].team_id == tc.pk
    assert result[3].team_id == td.pk


@pytest.mark.django_db
def test_get_predicted_group_standings_partial_predictions(user, pool, group_a_teams, group_a_matches):
    ta, tb, tc, td = group_a_teams
    # Only predict one match
    first_match = group_a_matches[0]
    Prediction.objects.create(
        user=user, pool=pool, match=first_match,
        predicted_home_score=1, predicted_away_score=0,
    )
    result = get_predicted_group_standings(user, pool, "A")
    # Should return standings for both teams in the predicted match
    assert len(result) == 2
    team_ids = {s.team_id for s in result}
    assert ta.pk in team_ids
    assert tb.pk in team_ids


@pytest.mark.django_db
def test_get_predicted_group_standings_no_predictions(user, pool, group_a_teams, group_a_matches):
    result = get_predicted_group_standings(user, pool, "A")
    assert result == []
