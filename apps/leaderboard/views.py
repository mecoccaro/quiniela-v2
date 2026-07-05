import datetime
from collections import defaultdict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.leaderboard.race import build_race_data
from apps.pools.models import (
    LeaderboardEntry,
    Pool,
    PoolChampionPick,
    PoolMembership,
    PoolTopScorerPick,
    Prediction,
)
from apps.tournaments.models import Match, Team
from apps.tournaments.services import (
    build_predicted_knockout_bracket,
    get_predicted_group_standings,
)
from apps.users.models import User

STAGE_LABELS = {
    "group": "Fase de Grupos",
    "r32": "Ronda de 32",
    "r16": "Octavos de final",
    "qf": "Cuartos de final",
    "sf": "Semifinales",
    "third_place": "Tercer puesto",
    "final": "Final",
}

KO_STAGE_ORDER = ("r32", "r16", "qf", "sf", "final")


class LeaderboardView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)

        entries = (
            LeaderboardEntry.objects.filter(pool=pool)
            .select_related("user")
            .order_by("rank", "user__nickname")
        )
        submitted_ids = set(
            PoolMembership.objects.filter(pool=pool, predictions_submitted=True)
            .values_list("user_id", flat=True)
        )
        context = {
            "pool": pool,
            "entries": entries,
            "submitted_ids": submitted_ids,
        }
        # Return only the polling partial when requested via HTMX to avoid nesting
        if request.headers.get("HX-Request"):
            return render(request, "leaderboard/partials/leaderboard_table.html", context)
        return render(request, "leaderboard/leaderboard.html", context)


def _build_predictions_context(target_user: User, pool: Pool) -> dict:
    """Build the read-only predictions context (group stage + knockout bracket
    + final picks) for a single participant. Shared by the "mis picks" view and
    the per-participant "ver picks" view."""
    tournament = pool.tournament

    # ── Group stage: matches + predicted standings ───────────────────────────
    group_matches = (
        Match.objects.filter(tournament=tournament, stage=Match.Stage.GROUP)
        .select_related("home_team", "away_team")
        .order_by("group_letter", "id")
    )
    pred_map = {
        p.match_id: p
        for p in Prediction.objects.filter(user=target_user, pool=pool)
        .select_related("predicted_winner")
    }

    groups: dict[str, list] = {}
    for match in group_matches:
        groups.setdefault(match.group_letter, []).append(
            {"match": match, "prediction": pred_map.get(match.pk)}
        )

    team_ids = {m.home_team_id for m in group_matches} | {m.away_team_id for m in group_matches}
    team_map = {t.pk: t for t in Team.objects.filter(pk__in=team_ids)}

    group_data = []
    for letter in sorted(groups.keys()):
        standings = get_predicted_group_standings(target_user, pool, letter)
        enriched = [(s, team_map.get(s.team_id)) for s in standings]
        group_data.append(
            {"letter": letter, "matches": groups[letter], "standings": enriched}
        )

    # ── Knockout: bracket tree (bracket_json) + per-match list with points ──
    ko_stages: list[dict] = []
    bracket_json: dict[str, list] = {}
    try:
        bracket = build_predicted_knockout_bracket(target_user, pool)
    except Exception:
        bracket = {}  # bracket may fail if group predictions are incomplete

    for key in KO_STAGE_ORDER:
        slots = bracket.get(key, [])
        if not slots:
            continue
        ko_stages.append(
            {"key": key, "label": STAGE_LABELS.get(key, key), "slots": slots}
        )
        bracket_json[key] = [
            {
                "home": slot.home_team.name if slot.home_team else "TBD",
                "homeCode": slot.home_team.fifa_code if slot.home_team else None,
                "away": slot.away_team.name if slot.away_team else "TBD",
                "awayCode": slot.away_team.fifa_code if slot.away_team else None,
                "homeScore": slot.prediction.predicted_home_score if slot.prediction else None,
                "awayScore": slot.prediction.predicted_away_score if slot.prediction else None,
                "slotKey": slot.slot_key,
                "matchPk": slot.match.pk if slot.match else None,
            }
            for slot in slots
        ]

    champion_pick = PoolChampionPick.objects.filter(user=target_user, pool=pool).first()
    top_scorer_pick = PoolTopScorerPick.objects.filter(user=target_user, pool=pool).first()
    entry = LeaderboardEntry.objects.filter(user=target_user, pool=pool).first()
    total_points = entry.total_points if entry else 0

    return {
        "group_data": group_data,
        "ko_stages": ko_stages,
        "bracket_json": bracket_json,
        "champion_pick": champion_pick,
        "top_scorer_pick": top_scorer_pick,
        "total_points": total_points,
    }


class MyPredictionsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        pool = get_object_or_404(Pool, pk=pool_id)
        membership = get_object_or_404(PoolMembership, pool=pool, user=user)

        context = _build_predictions_context(user, pool)
        context.update({
            "pool": pool,
            "membership": membership,
            "is_self": True,
            "viewing_user": user,
        })
        return render(request, "leaderboard/my_predictions.html", context)


class ParticipantPicksView(LoginRequiredMixin, View):
    """Read-only view of another participant's picks, mirroring "mis picks"."""

    def get(self, request: HttpRequest, pool_id: int, user_id: int) -> HttpResponse:
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)

        if user_id == request.user.pk:
            return MyPredictionsView.as_view()(request, pool_id=pool_id)

        target_membership = get_object_or_404(
            PoolMembership.objects.select_related("user"), pool=pool, user_id=user_id
        )

        # Don't reveal a participant's picks until they have submitted/locked.
        if not target_membership.predictions_submitted:
            return render(request, "leaderboard/participant_picks_locked.html", {
                "pool": pool,
                "viewing_user": target_membership.user,
            })

        context = _build_predictions_context(target_membership.user, pool)
        context.update({
            "pool": pool,
            "membership": target_membership,
            "is_self": False,
            "viewing_user": target_membership.user,
        })
        return render(request, "leaderboard/my_predictions.html", context)


class ParticipantsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)

        memberships = pool.memberships.select_related("user").order_by("user__nickname")

        user_ids = [m.user_id for m in memberships]
        champion_map = {
            p.user_id: p
            for p in PoolChampionPick.objects.filter(pool=pool, user_id__in=user_ids).select_related("team")
        }
        top_scorer_map = {
            p.user_id: p
            for p in PoolTopScorerPick.objects.filter(pool=pool, user_id__in=user_ids)
        }
        points_map = {
            e.user_id: e
            for e in LeaderboardEntry.objects.filter(pool=pool, user_id__in=user_ids)
        }

        participants = []
        for m in memberships:
            uid = m.user_id
            participants.append({
                "user": m.user,
                "predictions_submitted": m.predictions_submitted,
                "champion_pick": champion_map.get(uid) if m.predictions_submitted else None,
                "top_scorer_pick": top_scorer_map.get(uid) if m.predictions_submitted else None,
                "entry": points_map.get(uid),
            })

        return render(request, "leaderboard/participants.html", {
            "pool": pool,
            "participants": participants,
        })


class ScoringGuideView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)
        return render(request, "leaderboard/scoring_guide.html", {"pool": pool})


class PredictionDistributionView(LoginRequiredMixin, View):
    """How popular each team is at each knockout stage, across all submitted
    participants. Based only on participants who have submitted (they have a
    complete predicted bracket + champion pick). The champion column is
    expandable to reveal who picked each team as champion."""

    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)

        memberships = (
            PoolMembership.objects.filter(pool=pool, predictions_submitted=True)
            .select_related("user")
        )

        champ_count: dict[int, int] = defaultdict(int)
        sub_count: dict[int, int] = defaultdict(int)
        top4_count: dict[int, int] = defaultdict(int)
        top8_count: dict[int, int] = defaultdict(int)
        top16_count: dict[int, int] = defaultdict(int)
        champ_participants: dict[int, list] = defaultdict(list)
        all_team_ids: set[int] = set()

        n = 0
        for m in memberships:
            user = m.user
            try:
                bracket = build_predicted_knockout_bracket(user, pool)
            except Exception:
                continue
            if not bracket.get("final"):
                continue
            n += 1

            t16 = self._teams_in(bracket, "r16")
            t8 = self._teams_in(bracket, "qf")
            t4 = self._teams_in(bracket, "sf")
            for tid in t16:
                top16_count[tid] += 1
            for tid in t8:
                top8_count[tid] += 1
            for tid in t4:
                top4_count[tid] += 1
            all_team_ids |= t16

            champ_id, runner_id = self._final_result(bracket.get("final", []))
            if champ_id:
                champ_count[champ_id] += 1
                champ_participants[champ_id].append(user)
                all_team_ids.add(champ_id)
            if runner_id:
                sub_count[runner_id] += 1
                all_team_ids.add(runner_id)

        team_map = {t.pk: t for t in Team.objects.filter(pk__in=all_team_ids)}

        def pct(c: int) -> int:
            return round(c / n * 100) if n else 0

        rows = []
        for tid, team in team_map.items():
            rows.append({
                "team": team,
                "champ_count": champ_count[tid], "champ_pct": pct(champ_count[tid]),
                "sub_count": sub_count[tid], "sub_pct": pct(sub_count[tid]),
                "top4_count": top4_count[tid], "top4_pct": pct(top4_count[tid]),
                "top8_count": top8_count[tid], "top8_pct": pct(top8_count[tid]),
                "top16_count": top16_count[tid], "top16_pct": pct(top16_count[tid]),
                "champ_participants": sorted(
                    champ_participants[tid],
                    key=lambda u: (u.get_full_name() or u.nickname).lower(),
                ),
            })
        rows.sort(key=lambda r: (-r["champ_count"], -r["top16_count"], r["team"].name))

        return render(request, "leaderboard/distribution.html", {
            "pool": pool,
            "rows": rows,
            "participant_count": n,
        })

    @staticmethod
    def _teams_in(bracket: dict, stage: str) -> set[int]:
        """Team ids that reached `stage` in this predicted bracket."""
        ids: set[int] = set()
        for slot in bracket.get(stage, []):
            if slot.home_team:
                ids.add(slot.home_team.pk)
            if slot.away_team:
                ids.add(slot.away_team.pk)
        return ids

    @staticmethod
    def _final_result(final_slots) -> tuple[int | None, int | None]:
        """Return (champion_team_id, runner_up_team_id) from the Final slot."""
        if not final_slots:
            return None, None
        fs = final_slots[0]
        pred = fs.prediction
        home = fs.home_team.pk if fs.home_team else None
        away = fs.away_team.pk if fs.away_team else None
        if not pred or home is None or away is None:
            return None, None
        champ: int | None = None
        if pred.predicted_winner_id:
            champ = pred.predicted_winner_id
        elif pred.predicted_home_score is not None and pred.predicted_away_score is not None:
            if pred.predicted_home_score > pred.predicted_away_score:
                champ = home
            elif pred.predicted_away_score > pred.predicted_home_score:
                champ = away
        if champ is None:
            return None, None
        runner = away if champ == home else home
        return champ, runner


class PoolDayView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        pool = get_object_or_404(Pool, pk=pool_id)
        get_object_or_404(PoolMembership, pool=pool, user=request.user)

        date_str = request.GET.get("date")
        selected_date = datetime.date.fromisoformat(date_str) if date_str else datetime.date.today()

        matches = (
            Match.objects.filter(
                tournament=pool.tournament,
                scheduled_at__date=selected_date,
            )
            .select_related("home_team", "away_team")
            .order_by("scheduled_at")
        )

        memberships = PoolMembership.objects.filter(
            pool=pool, predictions_submitted=True
        ).select_related("user")

        # For knockout matches the two teams differ per participant (each one
        # predicted their own bracket). Build each participant's bracket once and
        # index its slots by bracket_slot so we can show the team codes they put.
        has_ko = any(m.stage != Match.Stage.GROUP for m in matches)
        user_slot_maps: dict[int, dict] = {}
        if has_ko:
            for m in memberships:
                try:
                    bracket = build_predicted_knockout_bracket(m.user, pool)
                except Exception:
                    continue
                slot_map = {}
                for slots in bracket.values():
                    for slot in slots:
                        slot_map[slot.slot_key] = slot
                user_slot_maps[m.user_id] = slot_map

        match_data = []
        for match in matches:
            is_ko = match.stage != Match.Stage.GROUP
            preds = Prediction.objects.filter(
                pool=pool, match=match
            ).select_related("user", "predicted_winner")
            pred_by_user = {p.user_id: p for p in preds}
            participants = []
            for m in memberships:
                item = {"user": m.user, "prediction": pred_by_user.get(m.user_id)}
                if is_ko:
                    slot = user_slot_maps.get(m.user_id, {}).get(match.bracket_slot)
                    if slot:
                        item["home_code"] = slot.home_team.fifa_code if slot.home_team else None
                        item["away_code"] = slot.away_team.fifa_code if slot.away_team else None
                participants.append(item)
            match_data.append({"match": match, "participants": participants, "is_ko": is_ko})

        available_dates = list(
            Match.objects.filter(tournament=pool.tournament, scheduled_at__isnull=False)
            .dates("scheduled_at", "day")
        )

        prev_date = None
        next_date = None
        for d in available_dates:
            if d < selected_date:
                prev_date = d
            elif d > selected_date and next_date is None:
                next_date = d

        return render(request, "leaderboard/pool_day.html", {
            "pool": pool,
            "selected_date": selected_date,
            "match_data": match_data,
            "available_dates": available_dates,
            "prev_date": prev_date,
            "next_date": next_date,
        })


class RaceView(LoginRequiredMixin, View):
    """Hidden bar-chart-race page. No navigation links point here; only staff
    (admin) users may load it — anyone else gets a 404 so the route's existence
    stays concealed. Grows automatically as results are entered."""

    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        if not request.user.is_staff:
            raise Http404
        pool = get_object_or_404(Pool, pk=pool_id)
        return render(request, "leaderboard/race.html", {
            "pool": pool,
            "race_data": build_race_data(pool),
        })
