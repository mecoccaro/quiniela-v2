import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from apps.pools.models import (
    LeaderboardEntry,
    Pool,
    PoolChampionPick,
    PoolMembership,
    PoolTopScorerPick,
    Prediction,
)
from apps.tournaments.models import Match
from apps.tournaments.services import build_predicted_knockout_bracket
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


class MyPredictionsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        pool = get_object_or_404(Pool, pk=pool_id)
        membership = get_object_or_404(PoolMembership, pool=pool, user=user)

        predictions = (
            Prediction.objects.filter(user=user, pool=pool)
            .select_related("match__home_team", "match__away_team", "predicted_winner")
            .order_by("match__stage", "match__group_letter", "match__id")
        )

        # Build knockout bracket to resolve actual team names for knockout slots
        # (knockout Match records have home_team/away_team = None until official results)
        ko_team_map: dict[int, tuple] = {}
        try:
            bracket = build_predicted_knockout_bracket(user, pool)
            for stage_slots in bracket.values():
                for slot in stage_slots:
                    if slot.match:
                        ko_team_map[slot.match.pk] = (slot.home_team, slot.away_team)
        except Exception:
            pass  # bracket may fail if group predictions are incomplete

        stage_order = ["group", "r32", "r16", "qf", "sf", "third_place", "final"]
        grouped: dict[str, list] = {}
        for pred in predictions:
            stage = pred.match.stage
            grouped.setdefault(stage, []).append(pred)

        stages = []
        for s in stage_order:
            if s not in grouped:
                continue
            enriched = []
            for pred in grouped[s]:
                if pred.match.stage != "group" and pred.match.pk in ko_team_map:
                    home_team, away_team = ko_team_map[pred.match.pk]
                else:
                    home_team = pred.match.home_team
                    away_team = pred.match.away_team
                enriched.append({
                    "pred": pred,
                    "home_team": home_team,
                    "away_team": away_team,
                })
            stages.append({"key": s, "label": STAGE_LABELS.get(s, s), "predictions": enriched})

        champion_pick = PoolChampionPick.objects.filter(user=user, pool=pool).first()
        top_scorer_pick = PoolTopScorerPick.objects.filter(user=user, pool=pool).first()
        entry = LeaderboardEntry.objects.filter(user=user, pool=pool).first()
        total_points = entry.total_points if entry else 0

        return render(request, "leaderboard/my_predictions.html", {
            "pool": pool,
            "membership": membership,
            "stages": stages,
            "champion_pick": champion_pick,
            "top_scorer_pick": top_scorer_pick,
            "total_points": total_points,
        })


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

        match_data = []
        for match in matches:
            preds = Prediction.objects.filter(
                pool=pool, match=match
            ).select_related("user", "predicted_winner")
            pred_by_user = {p.user_id: p for p in preds}
            participants = [
                {"user": m.user, "prediction": pred_by_user.get(m.user_id)}
                for m in memberships
            ]
            match_data.append({"match": match, "participants": participants})

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
