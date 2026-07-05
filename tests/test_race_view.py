import pytest
from django.test import Client

from apps.leaderboard.race import build_race_data
from apps.pools.models import Pool, PoolMembership, Prediction
from apps.tournaments.models import Match, Team, Tournament
from apps.users.models import User


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="Race Cup", slug="race-cup")


@pytest.fixture
def pool(db, tournament):
    return Pool.objects.create(name="Race Pool", tournament=tournament)


def _user(email, nick, staff=False):
    u = User.objects.create_user(
        email=email, nickname=nick, password="TestPass123!",
        first_name="R", last_name="C",
    )
    if staff:
        u.is_staff = True
        u.save(update_fields=["is_staff"])
    return u


@pytest.fixture
def staff_client(db):
    _user("admin@example.com", "admin", staff=True)
    c = Client()
    c.login(username="admin@example.com", password="TestPass123!")
    return c


@pytest.fixture
def member_client(db):
    _user("member@example.com", "member")
    c = Client()
    c.login(username="member@example.com", password="TestPass123!")
    return c


@pytest.mark.django_db
def test_staff_can_load_race(staff_client, pool):
    resp = staff_client.get(f"/pool/{pool.pk}/race/")
    assert resp.status_code == 200
    assert b'id="race-data"' in resp.content


@pytest.mark.django_db
def test_non_staff_gets_404(member_client, pool):
    resp = member_client.get(f"/pool/{pool.pk}/race/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_anonymous_redirected_to_login(client, pool):
    resp = client.get(f"/pool/{pool.pk}/race/")
    assert resp.status_code in (302, 301)
    assert "/login" in resp.headers.get("Location", "").lower()


@pytest.mark.django_db
def test_build_race_data_accumulates_and_grows(pool, tournament):
    home = Team.objects.create(name="Home", fifa_code="HOM")
    away = Team.objects.create(name="Away", fifa_code="AWY")
    u1 = _user("u1@example.com", "Ana")
    u2 = _user("u2@example.com", "Beto")
    PoolMembership.objects.create(pool=pool, user=u1)
    PoolMembership.objects.create(pool=pool, user=u2)

    # only completed matches count; scheduled one is ignored
    m1 = Match.objects.create(
        tournament=tournament, stage=Match.Stage.GROUP, matchday=1,
        home_team=home, away_team=away, home_score=1, away_score=0,
        status=Match.Status.COMPLETED,
    )
    Match.objects.create(
        tournament=tournament, stage=Match.Stage.GROUP, matchday=1,
        home_team=home, away_team=away, status=Match.Status.SCHEDULED,
    )
    Prediction.objects.create(
        user=u1, pool=pool, match=m1, predicted_home_score=1,
        predicted_away_score=0, points_awarded=5, slot_bonus_awarded=2,
    )
    Prediction.objects.create(
        user=u2, pool=pool, match=m1, predicted_home_score=0,
        predicted_away_score=0, points_awarded=1, slot_bonus_awarded=0,
    )

    data = build_race_data(pool)
    assert data["pool"] == "Race Pool"
    # single stage present (group), no "acumulado" until >1 stage has data
    keys = [s["key"] for s in data["stages"]]
    assert keys == ["group"]
    group = data["stages"][0]
    assert len(group["frames"]) == 1  # only the completed match
    totals = dict(zip(group["participants"], group["cumulative"][-1], strict=True))
    assert totals["Ana"] == 7  # 5 + 2 bonus
    assert totals["Beto"] == 1
