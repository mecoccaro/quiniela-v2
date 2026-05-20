import pytest
from django.test import Client

from apps.pools.models import (
    LeaderboardEntry,
    Pool,
    PoolChampionPick,
    PoolMembership,
    PoolTopScorerPick,
)
from apps.tournaments.models import Team, Tournament
from apps.users.models import User


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="LB Cup", slug="lb-cup")


@pytest.fixture
def pool(db, tournament):
    return Pool.objects.create(name="LB Pool", tournament=tournament)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="lb@example.com", nickname="lbuser",
        password="TestPass123!", first_name="L", last_name="B",
    )


@pytest.fixture
def user2(db):
    return User.objects.create_user(
        email="lb2@example.com", nickname="lbuser2",
        password="TestPass123!", first_name="L", last_name="B2",
    )


@pytest.fixture
def membership(db, pool, user):
    return PoolMembership.objects.create(pool=pool, user=user)


@pytest.fixture
def submitted_membership(db, pool, user):
    return PoolMembership.objects.create(pool=pool, user=user, predictions_submitted=True)


@pytest.fixture
def client_logged_in(user):
    c = Client()
    c.login(username="lb@example.com", password="TestPass123!")
    return c


# ─── Leaderboard ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_leaderboard_returns_200(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/pool/{pool.pk}/leaderboard/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_leaderboard_shows_entries(client_logged_in, pool, user, membership):
    LeaderboardEntry.objects.create(pool=pool, user=user, total_points=10, rank=1)
    response = client_logged_in.get(f"/pool/{pool.pk}/leaderboard/")
    assert response.status_code == 200
    assert b"lbuser" in response.content
    assert b"10" in response.content


@pytest.mark.django_db
def test_leaderboard_requires_login(pool, membership):
    response = Client().get(f"/pool/{pool.pk}/leaderboard/")
    assert response.status_code == 302
    assert "/login" in response["Location"] or "login" in response["Location"]


@pytest.mark.django_db
def test_leaderboard_requires_membership(client_logged_in, tournament):
    other_pool = Pool.objects.create(name="Other", tournament=tournament)
    response = client_logged_in.get(f"/pool/{other_pool.pk}/leaderboard/")
    assert response.status_code == 404


# ─── My Predictions ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_my_predictions_returns_200(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/pool/{pool.pk}/my-predictions/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_my_predictions_requires_login(pool, membership):
    response = Client().get(f"/pool/{pool.pk}/my-predictions/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_my_predictions_shows_locked_badge(client_logged_in, pool, submitted_membership):
    response = client_logged_in.get(f"/pool/{pool.pk}/my-predictions/")
    assert response.status_code == 200
    assert "Bloqueado" in response.content.decode()


# ─── Participants ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_participants_returns_200(client_logged_in, pool, membership):
    response = client_logged_in.get(f"/pool/{pool.pk}/participants/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_participants_hides_picks_for_unsubmitted(client_logged_in, pool, user, user2, membership):
    PoolMembership.objects.create(pool=pool, user=user2, predictions_submitted=False)
    team = Team.objects.create(name="HiddenTeam", fifa_code="HDN")
    PoolChampionPick.objects.create(user=user2, pool=pool, team=team)
    PoolTopScorerPick.objects.create(user=user2, pool=pool, player_name="HiddenScorer")

    response = client_logged_in.get(f"/pool/{pool.pk}/participants/")
    assert response.status_code == 200
    assert b"HiddenTeam" not in response.content
    assert b"HiddenScorer" not in response.content


@pytest.mark.django_db
def test_participants_shows_picks_for_submitted(client_logged_in, pool, user, user2, membership):
    PoolMembership.objects.create(pool=pool, user=user2, predictions_submitted=True)
    team = Team.objects.create(name="VisibleTeam", fifa_code="VSB")
    PoolChampionPick.objects.create(user=user2, pool=pool, team=team)
    PoolTopScorerPick.objects.create(user=user2, pool=pool, player_name="VisibleScorer")

    response = client_logged_in.get(f"/pool/{pool.pk}/participants/")
    assert response.status_code == 200
    assert b"VisibleTeam" in response.content
    assert b"VisibleScorer" in response.content
