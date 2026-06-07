from django.conf import settings
from django.db import models

from apps.tournaments.models import Match, Team, Tournament


class Pool(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        LOCKED = "locked", "Locked"
        COMPLETED = "completed", "Completed"

    name = models.CharField(max_length=100)
    tournament = models.ForeignKey(Tournament, on_delete=models.PROTECT, related_name="pools")
    status = models.CharField(max_length=20, choices=Status, default=Status.OPEN)
    lock_deadline = models.DateTimeField(null=True, blank=True)
    scoring_config = models.JSONField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.tournament})"


class PoolMembership(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(auto_now_add=True)
    predictions_submitted = models.BooleanField(default=False)

    class Meta:
        unique_together = [("pool", "user")]

    def __str__(self) -> str:
        return f"{self.user} in {self.pool}"


class Prediction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="predictions")
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")
    predicted_home_score = models.PositiveIntegerField()
    predicted_away_score = models.PositiveIntegerField()
    predicted_winner = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predicted_wins",
    )
    points_awarded = models.IntegerField(null=True, blank=True)
    slot_bonus_awarded = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "pool", "match")]

    def __str__(self) -> str:
        return f"{self.user} — {self.match} ({self.pool})"


class PoolChampionPick(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="champion_picks")
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="champion_picks")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="champion_picks")
    points_awarded = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "pool")]

    def __str__(self) -> str:
        return f"{self.user} picks {self.team} ({self.pool})"


class PoolTopScorerPick(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="top_scorer_picks")
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="top_scorer_picks")
    player_name = models.CharField(max_length=100)
    points_awarded = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [("user", "pool")]

    def __str__(self) -> str:
        return f"{self.user} picks {self.player_name} ({self.pool})"


class ThirdPlaceTiebreakerPick(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE)
    team = models.ForeignKey("tournaments.Team", on_delete=models.CASCADE)
    predicted_rank = models.PositiveIntegerField()

    class Meta:
        unique_together = [("user", "pool", "team")]

    def __str__(self) -> str:
        return f"{self.user} ranks {self.team} #{self.predicted_rank} ({self.pool})"


class LeaderboardEntry(models.Model):
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="leaderboard_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leaderboard_entries")
    total_points = models.IntegerField(default=0)
    advancement_bonus_total = models.IntegerField(default=0)
    group_classification_bonus = models.IntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)
    previous_rank = models.PositiveIntegerField(null=True, blank=True)
    last_calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("pool", "user")]

    @property
    def rank_change(self) -> int | None:
        """Positive = moved up, negative = moved down, 0 = no change, None = first calculation."""
        if self.previous_rank is None:
            return None
        return self.previous_rank - self.rank

    def __str__(self) -> str:
        return f"{self.user} — {self.pool} (rank {self.rank}, {self.total_points} pts)"
