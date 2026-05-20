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
        return render(request, "leaderboard/leaderboard.html", {
            "pool": pool,
            "entries": entries,
        })


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

        stage_order = ["group", "r32", "r16", "qf", "sf", "third_place", "final"]
        grouped: dict[str, list] = {}
        for pred in predictions:
            stage = pred.match.stage
            grouped.setdefault(stage, []).append(pred)

        stages = [
            {"key": s, "label": STAGE_LABELS.get(s, s), "predictions": grouped[s]}
            for s in stage_order
            if s in grouped
        ]

        champion_pick = PoolChampionPick.objects.filter(user=user, pool=pool).first()
        top_scorer_pick = PoolTopScorerPick.objects.filter(user=user, pool=pool).first()

        return render(request, "leaderboard/my_predictions.html", {
            "pool": pool,
            "membership": membership,
            "stages": stages,
            "champion_pick": champion_pick,
            "top_scorer_pick": top_scorer_pick,
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
