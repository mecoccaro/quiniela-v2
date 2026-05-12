from typing import TYPE_CHECKING

from .standings import MatchResult, TeamStanding, calculate_group_standings

if TYPE_CHECKING:
    from apps.pools.models import Pool
    from apps.users.models import User


def get_predicted_group_standings(
    user: "User",
    pool: "Pool",
    group_letter: str,
) -> list[TeamStanding]:
    """
    Build group standings from a user's predictions for one group.
    Only matches with a prediction are included; unpredicted matches are skipped.
    """
    from apps.pools.models import Prediction
    from apps.tournaments.models import Match, TournamentTeam

    tournament = pool.tournament

    group_matches = Match.objects.filter(
        tournament=tournament,
        stage=Match.Stage.GROUP,
        group_letter=group_letter,
    ).select_related("home_team", "away_team")

    predictions = {
        p.match_id: p
        for p in Prediction.objects.filter(
            user=user,
            pool=pool,
            match__in=group_matches,
        )
    }

    match_results = [
        MatchResult(
            home_team_id=match.home_team_id,
            away_team_id=match.away_team_id,
            home_score=predictions[match.pk].predicted_home_score,
            away_score=predictions[match.pk].predicted_away_score,
        )
        for match in group_matches
        if match.pk in predictions
    ]

    fifa_rankings = {
        tt.team_id: tt.fifa_ranking
        for tt in TournamentTeam.objects.filter(
            tournament=tournament,
            group_letter=group_letter,
        )
    }

    return calculate_group_standings(match_results, fifa_rankings)
