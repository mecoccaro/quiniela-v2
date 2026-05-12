import pytest
from django.test import Client

from apps.pools.models import Pool, PoolMembership, Prediction
from apps.tournaments.models import Match, Team, Tournament, TournamentTeam
from apps.users.models import User


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="Test Cup", slug="test-cup-pv")


@pytest.fixture
def teams(db):
    return [Team.objects.create(name=f"Team {c}", fifa_code=f"P{c}") for c in "ABCD"]


@pytest.fixture
def group_setup(db, tournament, teams):
    for i, team in enumerate(teams, start=1):
        TournamentTeam.objects.create(
            tournament=tournament, team=team, group_letter="A", fifa_ranking=i
        )
    ta, tb, tc, td = teams
    for home, away in [(ta, tb), (ta, tc), (ta, td), (tb, tc), (tb, td), (tc, td)]:
        Match.objects.create(
            tournament=tournament, stage=Match.Stage.GROUP,
            group_letter="A", home_team=home, away_team=away,
        )
    return tournament


@pytest.fixture
def pool(db, group_setup):
    return Pool.objects.create(name="Test Pool", tournament=group_setup)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="pred@example.com", nickname="preduser",
        password="TestPass123!", first_name="P", last_name="U",
    )


@pytest.fixture
def membership(db, pool, user):
    return PoolMembership.objects.create(pool=pool, user=user)


@pytest.fixture
def client_logged_in(user):
    c = Client()
    c.login(username="pred@example.com", password="TestPass123!")
    return c


@pytest.mark.django_db
def test_group_stage_page_returns_200(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/group-stage/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_group_stage_page_shows_all_groups(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/group-stage/")
    assert b"Grupo A" in response.content


@pytest.mark.django_db
def test_unauthenticated_redirects_to_login(pool):
    c = Client()
    response = c.get(f"/predictions/pool/{pool.pk}/group-stage/")
    assert response.status_code == 302
    assert "/users/login/" in response["Location"]


@pytest.mark.django_db
def test_non_member_gets_404(pool, db):
    User.objects.create_user(
        email="other@example.com", nickname="other", password="pass", first_name="O", last_name="O"
    )
    c = Client()
    c.login(username="other@example.com", password="pass")
    response = c.get(f"/predictions/pool/{pool.pk}/group-stage/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_post_prediction_creates_record(client_logged_in, pool, membership, group_setup):
    match = Match.objects.filter(tournament=group_setup, stage=Match.Stage.GROUP).first()
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/match/{match.pk}/",
        {"predicted_home_score": 2, "predicted_away_score": 1},
    )
    assert response.status_code == 200
    assert Prediction.objects.filter(pool=pool, match=match).count() == 1


@pytest.mark.django_db
def test_post_prediction_updates_existing(client_logged_in, pool, membership, user, group_setup):
    match = Match.objects.filter(tournament=group_setup, stage=Match.Stage.GROUP).first()
    Prediction.objects.create(
        user=user, pool=pool, match=match,
        predicted_home_score=1, predicted_away_score=0,
    )
    client_logged_in.post(
        f"/predictions/pool/{pool.pk}/match/{match.pk}/",
        {"predicted_home_score": 3, "predicted_away_score": 2},
    )
    pred = Prediction.objects.get(user=user, pool=pool, match=match)
    assert pred.predicted_home_score == 3
    assert pred.predicted_away_score == 2


@pytest.mark.django_db
def test_post_returns_standings_partial_html(client_logged_in, pool, membership, group_setup):
    match = Match.objects.filter(tournament=group_setup, stage=Match.Stage.GROUP).first()
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/match/{match.pk}/",
        {"predicted_home_score": 1, "predicted_away_score": 0},
    )
    assert response.status_code == 200
    assert b"standings-A" in response.content


@pytest.mark.django_db
def test_post_forbidden_when_predictions_submitted(client_logged_in, pool, membership, group_setup):
    membership.predictions_submitted = True
    membership.save()
    match = Match.objects.filter(tournament=group_setup, stage=Match.Stage.GROUP).first()
    response = client_logged_in.post(
        f"/predictions/pool/{pool.pk}/match/{match.pk}/",
        {"predicted_home_score": 1, "predicted_away_score": 0},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_submitted_form_renders_readonly(client_logged_in, pool, membership):
    membership.predictions_submitted = True
    membership.save()
    response = client_logged_in.get(f"/predictions/pool/{pool.pk}/group-stage/")
    assert response.status_code == 200
    assert b"readonly" in response.content
