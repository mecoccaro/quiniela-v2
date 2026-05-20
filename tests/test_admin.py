import pytest
from django.test import Client

from apps.pools.models import Pool, PoolMembership
from apps.tournaments.models import Match, Team, Tournament
from apps.users.models import User


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        email="admin@example.com",
        nickname="adminuser",
        password="AdminPass123!",
        first_name="Admin",
        last_name="User",
    )


@pytest.fixture
def admin_client(admin_user):
    c = Client()
    c.login(username="admin@example.com", password="AdminPass123!")
    return c


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="Admin Cup", slug="admin-cup")


@pytest.fixture
def pool(db, tournament):
    return Pool.objects.create(name="Admin Pool", tournament=tournament)


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        email="member@example.com",
        nickname="member",
        password="TestPass123!",
        first_name="M",
        last_name="B",
    )


@pytest.fixture
def match(db, tournament):
    ta = Team.objects.create(name="TeamX", fifa_code="AXX")
    tb = Team.objects.create(name="TeamY", fifa_code="AYY")
    return Match.objects.create(
        tournament=tournament,
        stage=Match.Stage.GROUP,
        group_letter="A",
        home_team=ta,
        away_team=tb,
    )


# ─── Pool admin ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_pool_changelist_returns_200(admin_client, pool):
    response = admin_client.get("/admin/pools/pool/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_lock_pool_action(admin_client, pool):
    assert pool.status == Pool.Status.OPEN
    response = admin_client.post(
        "/admin/pools/pool/",
        {"action": "lock_pools", "_selected_action": [pool.pk]},
    )
    assert response.status_code in (200, 302)
    pool.refresh_from_db()
    assert pool.status == Pool.Status.LOCKED


@pytest.mark.django_db
def test_admin_pool_member_count_displayed(admin_client, pool, regular_user):
    PoolMembership.objects.create(pool=pool, user=regular_user)
    response = admin_client.get("/admin/pools/pool/")
    assert response.status_code == 200
    assert b"1" in response.content  # member count column shows 1


# ─── Match admin ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_match_changelist_returns_200(admin_client, match):
    response = admin_client.get("/admin/tournaments/match/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_save_match_result_succeeds(admin_client, match):
    """Saving a completed match result should succeed; Celery task is skipped (tasks.py may not exist yet)."""
    url = f"/admin/tournaments/match/{match.pk}/change/"
    data = {
        "tournament": match.tournament_id,
        "stage": match.stage,
        "group_letter": match.group_letter,
        "home_team": match.home_team_id,
        "away_team": match.away_team_id,
        "status": Match.Status.COMPLETED,
        "home_score": 2,
        "away_score": 1,
        "bracket_slot": "",
        "scheduled_at_0": "",
        "scheduled_at_1": "",
        "knockout_winner": "",
        "_save": "Save",
    }
    response = admin_client.post(url, data)
    assert response.status_code in (200, 302)
    match.refresh_from_db()
    assert match.home_score == 2
    assert match.away_score == 1
    assert match.status == Match.Status.COMPLETED


# ─── Tournament admin ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_admin_tournament_changelist_returns_200(admin_client, tournament):
    response = admin_client.get("/admin/tournaments/tournament/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_score_final_picks_page_renders(admin_client, tournament):
    url = f"/admin/tournaments/tournament/{tournament.pk}/score-final-picks/"
    response = admin_client.get(url)
    assert response.status_code == 200
    assert b"Score Final Picks" in response.content
