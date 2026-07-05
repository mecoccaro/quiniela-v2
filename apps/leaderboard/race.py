"""Bar-chart-race data builder.

Pure read-side aggregation over already-scored predictions. Produces, per pool,
a cumulative-points timeline for every stage that has at least one completed
match, plus an "acumulado" timeline that chains all stages chronologically.
Grows automatically as official results are entered (only COMPLETED matches
are included).
"""

from apps.pools.models import PoolMembership, Prediction
from apps.tournaments.models import Match

# Chronological stage order used for the per-stage tabs.
STAGE_ORDER = ("group", "r32", "r16", "qf", "sf", "third_place", "final")

STAGE_LABELS = {
    "group": "Fase de Grupos",
    "r32": "Ronda de 32",
    "r16": "Octavos de final",
    "qf": "Cuartos de final",
    "sf": "Semifinales",
    "third_place": "Tercer puesto",
    "final": "Final",
}


def _frame_label(m: Match) -> dict:
    home = m.home_team.fifa_code if m.home_team_id else "?"
    away = m.away_team.fifa_code if m.away_team_id else "?"
    score = f"{m.home_score}-{m.away_score}" if m.home_score is not None else "vs"
    dstr = m.scheduled_at.strftime("%d/%m") if m.scheduled_at else ""
    if m.stage == "group" and m.matchday:
        sub = f"J{m.matchday} · {dstr}"
    else:
        sub = f"{STAGE_LABELS.get(m.stage, m.stage)} · {dstr}"
    return {"label": f"{home} {score} {away}", "sub": sub}


def _timeline(members: dict[int, str], matches: list[Match], pts: dict[tuple[int, int], int]) -> dict:
    """Build a cumulative timeline for an ordered list of matches."""
    uids = list(members.keys())
    running = {uid: 0 for uid in uids}
    cumulative = []
    for m in matches:
        for uid in uids:
            running[uid] += pts.get((uid, m.id), 0)
        cumulative.append([running[uid] for uid in uids])
    return {
        "participants": [members[uid] for uid in uids],
        "frames": [_frame_label(m) for m in matches],
        "cumulative": cumulative,
    }


def build_race_data(pool) -> dict:
    """Return race data for one pool: {pool, stages:[{key,label,...timeline}]}."""
    members = {
        pm.user_id: (pm.user.nickname or pm.user.username)
        for pm in PoolMembership.objects.filter(pool=pool).select_related("user")
    }

    matches = list(
        Match.objects.filter(
            tournament=pool.tournament, status=Match.Status.COMPLETED
        )
        .select_related("home_team", "away_team")
        .order_by("scheduled_at", "id")
    )

    # points per (user, match) for this pool, only over completed matches
    match_ids = [m.id for m in matches]
    pts: dict[tuple[int, int], int] = {}
    for uid, mid, p, sb in Prediction.objects.filter(
        pool=pool, match_id__in=match_ids
    ).values_list("user_id", "match_id", "points_awarded", "slot_bonus_awarded"):
        pts[(uid, mid)] = pts.get((uid, mid), 0) + (p or 0) + (sb or 0)

    by_stage: dict[str, list[Match]] = {}
    for m in matches:
        by_stage.setdefault(m.stage, []).append(m)

    stages = []
    # Acumulado total first (default view), only when >1 stage has data
    if len({m.stage for m in matches}) > 1:
        stages.append({"key": "acumulado", "label": "Acumulado total", **_timeline(members, matches, pts)})

    for key in STAGE_ORDER:
        stage_matches = by_stage.get(key)
        if not stage_matches:
            continue
        stages.append({"key": key, "label": STAGE_LABELS[key], **_timeline(members, stage_matches, pts)})

    return {"pool": pool.name, "stages": stages}
