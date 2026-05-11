import pytest
from django.db import IntegrityError

from apps.pools.models import LeaderboardEntry, Pool, PoolMembership, Prediction
from apps.tournaments.models import Match, Team, Tournament, TournamentTeam
from apps.users.models import User


@pytest.fixture
def tournament(db):
    return Tournament.objects.create(name="2026 FIFA World Cup", slug="wc2026")


@pytest.fixture
def team_a(db):
    return Team.objects.create(name="Argentina", fifa_code="ARG")


@pytest.fixture
def team_b(db):
    return Team.objects.create(name="Brazil", fifa_code="BRA")


@pytest.fixture
def match(db, tournament, team_a, team_b):
    return Match.objects.create(
        tournament=tournament,
        stage=Match.Stage.GROUP,
        group_letter="A",
        home_team=team_a,
        away_team=team_b,
    )


@pytest.fixture
def pool(db, tournament):
    return Pool.objects.create(name="Test Pool", tournament=tournament)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="test@example.com",
        nickname="testuser",
        password="pass",
        first_name="Test",
        last_name="User",
    )


@pytest.mark.django_db
class TestTournament:
    def test_str(self, tournament):
        assert str(tournament) == "2026 FIFA World Cup"

    def test_slug_unique(self, tournament):
        with pytest.raises(IntegrityError):
            Tournament.objects.create(name="Duplicate", slug="wc2026")


@pytest.mark.django_db
class TestTeam:
    def test_str(self, team_a):
        assert str(team_a) == "Argentina (ARG)"

    def test_fifa_code_unique(self, team_a):
        with pytest.raises(IntegrityError):
            Team.objects.create(name="Other", fifa_code="ARG")


@pytest.mark.django_db
class TestTournamentTeam:
    def test_str(self, tournament, team_a):
        tt = TournamentTeam.objects.create(
            tournament=tournament, team=team_a, group_letter="A", fifa_ranking=1
        )
        assert "Argentina" in str(tt)
        assert "Group A" in str(tt)

    def test_unique_together(self, tournament, team_a):
        TournamentTeam.objects.create(
            tournament=tournament, team=team_a, group_letter="A", fifa_ranking=1
        )
        with pytest.raises(IntegrityError):
            TournamentTeam.objects.create(
                tournament=tournament, team=team_a, group_letter="B", fifa_ranking=1
            )


@pytest.mark.django_db
class TestMatch:
    def test_str(self, match):
        assert "Argentina" in str(match)
        assert "Brazil" in str(match)

    def test_default_status(self, match):
        assert match.status == Match.Status.SCHEDULED

    def test_score_nullable(self, match):
        assert match.home_score is None
        assert match.away_score is None


@pytest.mark.django_db
class TestPool:
    def test_str(self, pool, tournament):
        assert "Test Pool" in str(pool)

    def test_default_status(self, pool):
        assert pool.status == Pool.Status.OPEN


@pytest.mark.django_db
class TestPoolMembership:
    def test_unique_together(self, pool, user):
        PoolMembership.objects.create(pool=pool, user=user)
        with pytest.raises(IntegrityError):
            PoolMembership.objects.create(pool=pool, user=user)

    def test_default_not_submitted(self, pool, user):
        membership = PoolMembership.objects.create(pool=pool, user=user)
        assert membership.predictions_submitted is False


@pytest.mark.django_db
class TestPrediction:
    def test_create(self, user, pool, match):
        pred = Prediction.objects.create(
            user=user,
            pool=pool,
            match=match,
            predicted_home_score=2,
            predicted_away_score=1,
        )
        assert pred.points_awarded is None
        assert "Argentina" in str(pred)

    def test_unique_together(self, user, pool, match):
        Prediction.objects.create(
            user=user, pool=pool, match=match,
            predicted_home_score=1, predicted_away_score=0,
        )
        with pytest.raises(IntegrityError):
            Prediction.objects.create(
                user=user, pool=pool, match=match,
                predicted_home_score=2, predicted_away_score=0,
            )


@pytest.mark.django_db
class TestLeaderboardEntry:
    def test_create(self, pool, user):
        entry = LeaderboardEntry.objects.create(pool=pool, user=user)
        assert entry.total_points == 0
        assert entry.rank == 0
        assert "rank 0" in str(entry)

    def test_unique_together(self, pool, user):
        LeaderboardEntry.objects.create(pool=pool, user=user)
        with pytest.raises(IntegrityError):
            LeaderboardEntry.objects.create(pool=pool, user=user)
