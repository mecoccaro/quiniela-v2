from dataclasses import dataclass, field


@dataclass
class MatchResult:
    home_team_id: int
    away_team_id: int
    home_score: int
    away_score: int


@dataclass
class TeamStanding:
    team_id: int
    played: int = field(default=0)
    won: int = field(default=0)
    drawn: int = field(default=0)
    lost: int = field(default=0)
    goals_for: int = field(default=0)
    goals_against: int = field(default=0)
    goal_difference: int = field(default=0)
    points: int = field(default=0)
    position: int = field(default=0)


def _compute_h2h(
    team_ids: list[int], matches: list[MatchResult]
) -> dict[int, dict[str, int]]:
    id_set = set(team_ids)
    h2h: dict[int, dict[str, int]] = {t: {"pts": 0, "gd": 0, "gf": 0} for t in team_ids}
    for m in matches:
        if m.home_team_id in id_set and m.away_team_id in id_set:
            h2h[m.home_team_id]["gf"] += m.home_score
            h2h[m.away_team_id]["gf"] += m.away_score
            h2h[m.home_team_id]["gd"] += m.home_score - m.away_score
            h2h[m.away_team_id]["gd"] += m.away_score - m.home_score
            if m.home_score > m.away_score:
                h2h[m.home_team_id]["pts"] += 3
            elif m.home_score < m.away_score:
                h2h[m.away_team_id]["pts"] += 3
            else:
                h2h[m.home_team_id]["pts"] += 1
                h2h[m.away_team_id]["pts"] += 1
    return h2h


def _group_by_h2h(
    team_ids: list[int], matches: list[MatchResult]
) -> list[list[int]]:
    """Sort team_ids by H2H criteria (pts, GD, GF) and return groups of still-tied teams."""
    if len(team_ids) <= 1:
        return [team_ids]
    h2h = _compute_h2h(team_ids, matches)
    sorted_ids = sorted(
        team_ids,
        key=lambda t: (-h2h[t]["pts"], -h2h[t]["gd"], -h2h[t]["gf"]),
    )
    groups: list[list[int]] = []
    i = 0
    while i < len(sorted_ids):
        j = i + 1
        while j < len(sorted_ids) and (
            h2h[sorted_ids[j]]["pts"] == h2h[sorted_ids[i]]["pts"]
            and h2h[sorted_ids[j]]["gd"] == h2h[sorted_ids[i]]["gd"]
            and h2h[sorted_ids[j]]["gf"] == h2h[sorted_ids[i]]["gf"]
        ):
            j += 1
        groups.append(sorted_ids[i:j])
        i = j
    return groups


def _overall_sort(
    team_ids: list[int],
    overall: dict[int, TeamStanding],
    rankings: dict[int, int],
) -> list[int]:
    return sorted(
        team_ids,
        key=lambda t: (
            -overall[t].goal_difference,
            -overall[t].goals_for,
            rankings.get(t, 9999),
        ),
    )


def _break_ties(
    tied: list[int],
    matches: list[MatchResult],
    overall: dict[int, TeamStanding],
    rankings: dict[int, int],
    depth: int = 0,
) -> list[int]:
    """
    Recursively resolve ties using FIFA tiebreaker rules.
    depth=0: first H2H pass; depth=1: recursive H2H among still-tied; then overall criteria.
    """
    if len(tied) <= 1:
        return tied
    result: list[int] = []
    for sub_group in _group_by_h2h(tied, matches):
        if len(sub_group) <= 1:
            result.extend(sub_group)
        elif depth == 0:
            result.extend(_break_ties(sub_group, matches, overall, rankings, depth=1))
        else:
            result.extend(_overall_sort(sub_group, overall, rankings))
    return result


def calculate_group_standings(
    matches: list[MatchResult],
    fifa_rankings: dict[int, int],
) -> list[TeamStanding]:
    """Apply FIFA tiebreaker rules to produce ordered standings for one group."""
    team_ids: set[int] = set()
    for m in matches:
        team_ids.add(m.home_team_id)
        team_ids.add(m.away_team_id)

    standings: dict[int, TeamStanding] = {t: TeamStanding(team_id=t) for t in team_ids}

    for m in matches:
        h = standings[m.home_team_id]
        a = standings[m.away_team_id]
        h.played += 1
        a.played += 1
        h.goals_for += m.home_score
        h.goals_against += m.away_score
        a.goals_for += m.away_score
        a.goals_against += m.home_score
        if m.home_score > m.away_score:
            h.won += 1
            h.points += 3
            a.lost += 1
        elif m.home_score < m.away_score:
            a.won += 1
            a.points += 3
            h.lost += 1
        else:
            h.drawn += 1
            h.points += 1
            a.drawn += 1
            a.points += 1

    for s in standings.values():
        s.goal_difference = s.goals_for - s.goals_against

    by_points = sorted(team_ids, key=lambda t: -standings[t].points)

    ordered: list[int] = []
    i = 0
    while i < len(by_points):
        j = i + 1
        while (
            j < len(by_points)
            and standings[by_points[j]].points == standings[by_points[i]].points
        ):
            j += 1
        tied_group = by_points[i:j]
        if len(tied_group) == 1:
            ordered.extend(tied_group)
        else:
            ordered.extend(_break_ties(tied_group, matches, standings, fifa_rankings))
        i = j

    result = []
    for pos, tid in enumerate(ordered, start=1):
        s = standings[tid]
        s.position = pos
        result.append(s)
    return result


def rank_third_place_teams(
    third_place_teams: list[TeamStanding],
    fifa_rankings: dict[int, int],
) -> list[TeamStanding]:
    """Rank all third-place teams by points, GD, GF, FIFA ranking to find best 8."""
    return sorted(
        third_place_teams,
        key=lambda t: (
            -t.points,
            -t.goal_difference,
            -t.goals_for,
            fifa_rankings.get(t.team_id, 9999),
        ),
    )
