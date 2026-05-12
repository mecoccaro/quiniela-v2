import pytest
from django.test import Client

from apps.pools.models import (
    LeaderboardEntry,
    Pool,
    PoolChampionPick,
    PoolMembership,
    PoolTopScorerPick,
    Prediction,
)
from apps.tournaments.models import Match, Team, Tournament, TournamentTeam
from apps.users.models import User

# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="Test Cup", slug="test-cup-ko")


@pytest.fixture
def teams(db):
    return [Team.objects.create(name=f"Team {c}", fifa_code=f"K{c}") for c in "ABCD"]


@pytest.fixture
def group_setup(db, tournament, teams):
    ta, tb, tc, td = teams
    for i, team in enumerate(teams, start=1):
        TournamentTeam.objects.create(
            tournament=tournament, team=team, group_letter="A", fifa_ranking=i
        )
    matches = []
    for home, away in [(ta, tb), (ta, tc), (ta, td), (tb, tc), (tb, td), (tc, td)]:
        matches.append(Match.objects.create(
            tournament=tournament, stage=Match.Stage.GROUP, group_letter="A",
            home_team=home, away_team=away,
        ))
    return tournament, matches


@pytest.fixture
def ko_match(db, tournament):
    return Match.objects.create(
        tournament=tournament, stage=Match.Stage.R32, bracket_slot="R32_1"
    )


@pytest.fixture
def pool(db, group_setup):
    tournament, _ = group_setup
    return Pool.objects.create(name="Test Pool", tournament=tournament)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="ko@example.com", nickname="kouser",
        password="TestPass123!", first_name="K", last_name="O",
    )


@pytest.fixture
def membership(db, pool, user):
    return PoolMembership.objects.create(pool=pool, user=user)


@pytest.fixture
def client_logged_in(user):
    c = Client()
    c.login(username="ko@example.com", password="TestPass123!")
    return c


@pytest.fixture
def all_group_predictions(db, pool, user, group_setup):
    """Pre-fill all 6 group predictions so knockout page is accessible."""
    tournament, matches = group_setup
    for match in matches:
        Prediction.objects.create(
            user=user, pool=pool, match=match,
            predicted_home_score=1, predicted_away_score=0,
        )


# ─── Gating ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_knockout_page_requires_all_group_predictions(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/knockout/")
    assert response.status_code == 302
    assert "group-stage" in response["Location"]


@pytest.mark.django_db
def test_knockout_page_accessible_with_all_group_predictions(
    client_logged_in, pool, membership, all_group_predictions
):
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/knockout/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_knockout_page_unauthenticated_redirects(pool, group_setup):
    c = Client()
    response = c.get(f"/predictions/pool/{pool.pk}/knockout/")
    assert response.status_code == 302
    assert "/users/login/" in response["Location"]


# ─── Saving knockout predictions ──────────────────────────────────────────────

@pytest.mark.django_db
def test_save_knockout_prediction_creates_record(
    client_logged_in, pool, membership, ko_match, teams
):
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/knockout/match/{ko_match.pk}/",
        {"predicted_home_score": 2, "predicted_away_score": 1, "predicted_winner": ""},
    )
    assert response.status_code == 200
    assert Prediction.objects.filter(pool=pool, match=ko_match).count() == 1


@pytest.mark.django_db
def test_draw_prediction_requires_winner(client_logged_in, pool, membership, ko_match):
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/knockout/match/{ko_match.pk}/",
        {"predicted_home_score": 1, "predicted_away_score": 1, "predicted_winner": ""},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_draw_prediction_with_winner_saves(client_logged_in, pool, membership, ko_match, teams):
    winner = teams[0]
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/knockout/match/{ko_match.pk}/",
        {"predicted_home_score": 1, "predicted_away_score": 1, "predicted_winner": winner.pk},
    )
    assert response.status_code == 200
    pred = Prediction.objects.get(pool=pool, match=ko_match)
    assert pred.predicted_winner_id == winner.pk


@pytest.mark.django_db
def test_knockout_post_forbidden_when_submitted(
    client_logged_in, pool, membership, ko_match
):
    membership.predictions_submitted = True
    membership.save()
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/knockout/match/{ko_match.pk}/",
        {"predicted_home_score": 2, "predicted_away_score": 0, "predicted_winner": ""},
    )
    assert response.status_code == 403


# ─── Picks ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_picks_page_returns_200(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/picks/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_save_champion_pick(client_logged_in, pool, membership, teams):
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/picks/champion/",
        {"team_id": teams[0].pk},
    )
    assert response.status_code == 200
    assert PoolChampionPick.objects.filter(pool=pool).count() == 1


@pytest.mark.django_db
def test_save_top_scorer_pick(client_logged_in, pool, membership):
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/picks/top-scorer/",
        {"player_name": "Lionel Messi"},
    )
    assert response.status_code == 200
    pick = PoolTopScorerPick.objects.get(pool=pool)
    assert pick.player_name == "Lionel Messi"


# ─── Submission ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_locks_predictions(client_logged_in, pool, membership):
    response = client_logged_in.post(f"/predictions/pool/{pool.pk}/submit/")
    assert response.status_code == 302
    membership.refresh_from_db()
    assert membership.predictions_submitted is True


@pytest.mark.django_db
def test_submit_creates_leaderboard_entry(client_logged_in, pool, membership, user):
    client_logged_in.post(f"/predictions/pool/{pool.pk}/submit/")
    assert LeaderboardEntry.objects.filter(pool=pool, user=user).count() == 1


@pytest.mark.django_db
def test_submit_idempotent(client_logged_in, pool, membership, user):
    client_logged_in.post(f"/predictions/pool/{pool.pk}/submit/")
    client_logged_in.post(f"/predictions/pool/{pool.pk}/submit/")
    assert LeaderboardEntry.objects.filter(pool=pool, user=user).count() == 1


@pytest.mark.django_db
def test_submission_confirm_page_returns_200(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/submit/")
    assert response.status_code == 200
