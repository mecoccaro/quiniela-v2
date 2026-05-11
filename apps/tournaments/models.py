from django.db import models


class Tournament(models.Model):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        GROUP_STAGE = "group_stage", "Group Stage"
        KNOCKOUT = "knockout", "Knockout"
        COMPLETED = "completed", "Completed"

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.UPCOMING)
    num_groups = models.PositiveIntegerField(default=12)
    teams_per_group = models.PositiveIntegerField(default=4)
    third_place_advancers = models.PositiveIntegerField(default=8)
    scoring_config = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    fifa_code = models.CharField(max_length=3, unique=True)
    flag_url = models.URLField(blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.fifa_code})"


class TournamentTeam(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="tournament_teams")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="tournament_teams")
    group_letter = models.CharField(max_length=1)
    fifa_ranking = models.PositiveIntegerField()

    class Meta:
        unique_together = [("tournament", "team")]

    def __str__(self) -> str:
        return f"{self.team} — Group {self.group_letter} ({self.tournament})"


class Match(models.Model):
    class Stage(models.TextChoices):
        GROUP = "group", "Group Stage"
        R32 = "r32", "Round of 32"
        R16 = "r16", "Round of 16"
        QF = "qf", "Quarter-Final"
        SF = "sf", "Semi-Final"
        THIRD_PLACE = "third_place", "Third Place"
        FINAL = "final", "Final"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        COMPLETED = "completed", "Completed"

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name="matches")
    stage = models.CharField(max_length=20, choices=Stage)
    group_letter = models.CharField(max_length=1, blank=True)
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_matches")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    home_score = models.PositiveIntegerField(null=True, blank=True)
    away_score = models.PositiveIntegerField(null=True, blank=True)
    knockout_winner = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knockout_wins",
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.SCHEDULED)

    class Meta:
        indexes = [
            models.Index(fields=["tournament", "stage", "group_letter"]),
        ]

    def __str__(self) -> str:
        return f"{self.home_team} vs {self.away_team} ({self.stage})"
