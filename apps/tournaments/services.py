import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .standings import MatchResult, TeamStanding, calculate_group_standings, rank_third_place_teams

if TYPE_CHECKING:
    from apps.pools.models import Pool, Prediction
    from apps.tournaments.models import Match, Team
    from apps.users.models import User

KNOCKOUT_BRACKET_PATH = Path(__file__).resolve().parents[2] / "data" / "knockout_bracket.json"


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
        and match.home_team_id is not None
        and match.away_team_id is not None
    ]

    fifa_rankings = {
        tt.team_id: tt.fifa_ranking
        for tt in TournamentTeam.objects.filter(
            tournament=tournament,
            group_letter=group_letter,
        )
    }

    return calculate_group_standings(match_results, fifa_rankings)


@dataclass
class BracketSlot:
    slot_key: str
    home_team: "Team | None"
    away_team: "Team | None"
    match: "Match | None"
    prediction: "Prediction | None"


def _resolve_team(
    descriptor: str,
    position_map: dict[str, "int | None"],
    third_ids: "list[int | None]",
    winner_map: "dict[str, int | None]",
) -> "int | None":
    """Resolve a bracket descriptor like 'A1', '3RD_2', 'win:R32_5' to a team_id."""
    if descriptor.startswith("win:"):
        return winner_map.get(descriptor[4:])
    if descriptor.startswith("3RD_"):
        idx = int(descriptor[4:]) - 1
        return third_ids[idx] if idx < len(third_ids) else None
    return position_map.get(descriptor)


def build_predicted_knockout_bracket(
    user: "User",
    pool: "Pool",
) -> "dict[str, list[BracketSlot]]":
    """
    Build the full knockout bracket from user's group and knockout predictions.
    Returns {stage_key: [BracketSlot, ...]} for r32, r16, qf, sf, final.
    """
    from apps.pools.models import Prediction
    from apps.tournaments.models import Match, Team, TournamentTeam

    tournament = pool.tournament
    bracket_data = json.loads(KNOCKOUT_BRACKET_PATH.read_text())

    # Group letters in the tournament
    group_letters = sorted(
        Match.objects.filter(tournament=tournament, stage=Match.Stage.GROUP)
        .values_list("group_letter", flat=True)
        .distinct()
    )

    # FIFA rankings for tiebreaker
    fifa_rankings = {
        tt.team_id: tt.fifa_ranking
        for tt in TournamentTeam.objects.filter(tournament=tournament)
    }

    # All teams in this tournament
    all_teams: dict[int, Team] = {
        t.pk: t
        for t in Team.objects.filter(tournament_teams__tournament=tournament)
    }

    # Build position map {"A1": team_id, ...} and collect third-place finishers
    position_map: dict[str, int | None] = {}
    third_place_standings: list[TeamStanding] = []

    for letter in group_letters:
        standings = get_predicted_group_standings(user, pool, letter)
        for s in standings:
            position_map[f"{letter}{s.position}"] = s.team_id
            if s.position == 3:
                third_place_standings.append(s)

    # Rank best 8 third-place teams
    ranked_third = rank_third_place_teams(third_place_standings, fifa_rankings)
    third_ids: list[int | None] = [s.team_id for s in ranked_third[:8]]
    while len(third_ids) < 8:
        third_ids.append(None)

    # All knockout placeholder matches, keyed by bracket_slot
    knockout_matches: dict[str, Match] = {
        m.bracket_slot: m
        for m in Match.objects.filter(tournament=tournament).exclude(bracket_slot="")
    }

    # All user predictions for those matches
    ko_match_ids = [m.pk for m in knockout_matches.values()]
    ko_predictions: dict[int, Prediction] = {
        p.match_id: p
        for p in Prediction.objects.filter(user=user, pool=pool, match_id__in=ko_match_ids)
    }

    # Build winner map {slot_key: team_id} from predicted_winner on each prediction
    winner_map: dict[str, int | None] = {
        slot: (ko_predictions[m.pk].predicted_winner_id if ko_predictions.get(m.pk) else None)
        for slot, m in knockout_matches.items()
    }

    result: dict[str, list[BracketSlot]] = {}
    for stage_key in ("r32", "r16", "qf", "sf", "final"):
        if stage_key not in bracket_data:
            continue
        slots = []
        for slot_def in bracket_data[stage_key]:
            slot_key = slot_def["slot"]
            home_id = _resolve_team(slot_def["home"], position_map, third_ids, winner_map)
            away_id = _resolve_team(slot_def["away"], position_map, third_ids, winner_map)
            match = knockout_matches.get(slot_key)
            prediction = ko_predictions.get(match.pk) if match else None
            slots.append(BracketSlot(
                slot_key=slot_key,
                home_team=all_teams.get(home_id) if home_id else None,
                away_team=all_teams.get(away_id) if away_id else None,
                match=match,
                prediction=prediction,
            ))
        result[stage_key] = slots

    return result
