import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .standings import MatchResult, TeamStanding, calculate_group_standings, rank_third_place_teams

if TYPE_CHECKING:
    from apps.pools.models import Pool, Prediction
    from apps.tournaments.models import Match, Team, Tournament
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

    tournament_teams = TournamentTeam.objects.filter(
        tournament=tournament,
        group_letter=group_letter,
    )
    fifa_rankings = {tt.team_id: tt.fifa_ranking for tt in tournament_teams}
    conduct_scores = {tt.team_id: tt.conduct_score for tt in tournament_teams}

    return calculate_group_standings(match_results, fifa_rankings, conduct_scores)


def get_actual_group_standings(
    tournament: "Tournament",
    group_letter: str,
) -> "list[TeamStanding]":
    """Compute actual standings for a group from official match results."""
    from apps.tournaments.models import Match, TournamentTeam

    matches = Match.objects.filter(
        tournament=tournament,
        stage=Match.Stage.GROUP,
        group_letter=group_letter,
        status=Match.Status.COMPLETED,
    ).select_related("home_team", "away_team")

    results = [
        MatchResult(m.home_team_id, m.away_team_id, m.home_score, m.away_score)
        for m in matches
        if m.home_team_id is not None
        and m.away_team_id is not None
        and m.home_score is not None
        and m.away_score is not None
    ]

    if not results:
        return []

    tournament_teams = TournamentTeam.objects.filter(
        tournament=tournament,
        group_letter=group_letter,
    )
    rankings = {tt.team_id: tt.fifa_ranking for tt in tournament_teams if tt.fifa_ranking is not None}
    conduct = {tt.team_id: tt.conduct_score for tt in tournament_teams}
    return calculate_group_standings(results, rankings, conduct)


def _get_all_third_place_standings(
    user: "User",
    pool: "Pool",
) -> "tuple[list[TeamStanding], dict[int, int]]":
    """Return (third_place_standings, fifa_rankings) across all groups."""
    from apps.tournaments.models import Match, TournamentTeam

    tournament = pool.tournament
    group_letters = sorted(
        Match.objects.filter(tournament=tournament, stage=Match.Stage.GROUP)
        .values_list("group_letter", flat=True)
        .distinct()
    )
    fifa_rankings = {
        tt.team_id: tt.fifa_ranking
        for tt in TournamentTeam.objects.filter(tournament=tournament)
    }
    third_place_standings = []
    for letter in group_letters:
        group_standings = get_predicted_group_standings(user, pool, letter)
        for s in group_standings:
            if s.position == 3:
                third_place_standings.append(s)
    return third_place_standings, fifa_rankings


def needs_conduct_tiebreaker(user: "User", pool: "Pool") -> bool:
    """Return True if the user's third-place rankings have a conduct-level tie at position 8/9."""
    third_place_standings, fifa_rankings = _get_all_third_place_standings(user, pool)
    if len(third_place_standings) < 9:
        return False
    ranked = rank_third_place_teams(third_place_standings, fifa_rankings)
    t8 = ranked[7]
    t9 = ranked[8]
    return (
        t8.points == t9.points
        and t8.goal_difference == t9.goal_difference
        and t8.goals_for == t9.goals_for
        and t8.conduct_score == 0
        and t9.conduct_score == 0
    )


def get_conduct_tied_thirds(user: "User", pool: "Pool") -> "list":
    """Return the Team objects involved in the conduct-level tie for the 8th-place third."""
    from apps.tournaments.models import Team

    third_place_standings, fifa_rankings = _get_all_third_place_standings(user, pool)
    if len(third_place_standings) < 9:
        return []
    ranked = rank_third_place_teams(third_place_standings, fifa_rankings)
    t8 = ranked[7]
    tied_team_ids = [
        s.team_id
        for s in ranked
        if s.points == t8.points
        and s.goal_difference == t8.goal_difference
        and s.goals_for == t8.goals_for
    ]
    return list(Team.objects.filter(pk__in=tied_team_ids))


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
    third_pool_map: "dict[str, int | None]",
    winner_map: "dict[str, int | None]",
    loser_map: "dict[str, int | None] | None" = None,
) -> "int | None":
    """Resolve a bracket descriptor like 'A1', '3RD_ABCDF', 'win:R32_1', 'lose:SF_1'."""
    if descriptor.startswith("win:"):
        return winner_map.get(descriptor[4:])
    if descriptor.startswith("lose:"):
        return (loser_map or {}).get(descriptor[5:])
    if descriptor.upper().startswith("3RD_"):
        return third_pool_map.get(descriptor.upper())
    return position_map.get(descriptor)


def _build_third_pool_map(
    r32_slots: "list[dict]",
    ranked_third: "list[TeamStanding]",
    third_group_letter: "dict[int, str]",
) -> "dict[str, int | None]":
    """
    Greedily assign ranked 3rd-place teams to pool-based descriptors (e.g. '3RD_ABCDF').
    Keys stored uppercase; iterates R32 slots in order, picks highest-ranked unassigned
    3rd-place team whose group letter is in the pool.
    """
    result: dict[str, int | None] = {}
    assigned: set[int] = set()
    for slot_def in r32_slots:
        for field in ("home", "away"):
            desc = slot_def[field]
            if not desc.upper().startswith("3RD_"):
                continue
            canonical = desc.upper()
            if canonical in result:
                continue
            pool_letters = set(canonical[4:])
            chosen = None
            for s in ranked_third:
                if s.team_id not in assigned and third_group_letter.get(s.team_id) in pool_letters:
                    chosen = s.team_id
                    assigned.add(s.team_id)
                    break
            result[canonical] = chosen
    return result


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

    # FIFA rankings for tiebreaker (used in rank_third_place_teams)
    all_tournament_teams = TournamentTeam.objects.filter(tournament=tournament)
    fifa_rankings = {tt.team_id: tt.fifa_ranking for tt in all_tournament_teams}

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

    # Apply tiebreaker picks if the user has submitted them
    from apps.pools.models import ThirdPlaceTiebreakerPick

    tiebreaker_picks = {
        p.team_id: p.predicted_rank
        for p in ThirdPlaceTiebreakerPick.objects.filter(user=user, pool=pool)
    }
    if tiebreaker_picks:
        ranked_third.sort(key=lambda s: tiebreaker_picks.get(s.team_id, 999))

    # Map team_id → group_letter for 3rd-place teams (needed for pool assignment)
    third_group_letter: dict[int, str] = {
        team_id: key[0]
        for key, team_id in position_map.items()
        if key.endswith("3") and team_id is not None
    }

    # Build pool-based third-place assignment for descriptors like '3rd_ABCDF'
    r32_slots = bracket_data.get("r32", [])
    third_pool_map = _build_third_pool_map(r32_slots, ranked_third[:8], third_group_letter)

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

    # winner_map and loser_map built stage-by-stage so later rounds can resolve teams.
    winner_map: dict[str, int | None] = {}
    loser_map: dict[str, int | None] = {}

    result: dict[str, list[BracketSlot]] = {}
    for stage_key in ("r32", "r16", "qf", "sf", "third_place", "final"):
        if stage_key not in bracket_data:
            continue
        slots = []
        for slot_def in bracket_data[stage_key]:
            slot_key = slot_def["slot"]
            home_id = _resolve_team(slot_def["home"], position_map, third_pool_map, winner_map, loser_map)
            away_id = _resolve_team(slot_def["away"], position_map, third_pool_map, winner_map, loser_map)
            match = knockout_matches.get(slot_key)
            pred = ko_predictions.get(match.pk) if match else None

            # Derive winner/loser so subsequent rounds can resolve their teams
            if pred:
                if pred.predicted_winner_id:
                    winner_map[slot_key] = pred.predicted_winner_id
                    loser_map[slot_key] = away_id if pred.predicted_winner_id == home_id else home_id
                elif pred.predicted_home_score > pred.predicted_away_score:
                    winner_map[slot_key] = home_id
                    loser_map[slot_key] = away_id
                elif pred.predicted_away_score > pred.predicted_home_score:
                    winner_map[slot_key] = away_id
                    loser_map[slot_key] = home_id

            slots.append(BracketSlot(
                slot_key=slot_key,
                home_team=all_teams.get(home_id) if home_id else None,
                away_team=all_teams.get(away_id) if away_id else None,
                match=match,
                prediction=pred,
            ))
        result[stage_key] = slots

    return result
