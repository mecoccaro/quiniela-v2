from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from apps.pools.models import Pool, PoolMembership, Prediction
from apps.tournaments.models import Match, Team
from apps.tournaments.services import get_predicted_group_standings
from apps.users.models import User

from .forms import MatchPredictionForm


class GroupPredictionsView(LoginRequiredMixin, TemplateView):
    template_name = "predictions/group_stage.html"

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        self.pool = get_object_or_404(Pool, pk=kwargs["pool_id"])
        self.membership = get_object_or_404(
            PoolMembership, pool=self.pool, user=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tournament = self.pool.tournament
        user: User = self.request.user

        all_matches = (
            Match.objects.filter(tournament=tournament, stage=Match.Stage.GROUP)
            .select_related("home_team", "away_team")
            .order_by("group_letter", "id")
        )

        pred_map = {
            p.match_id: p
            for p in Prediction.objects.filter(user=user, pool=self.pool)
        }

        groups: dict = {}
        for match in all_matches:
            g = match.group_letter
            if g not in groups:
                groups[g] = []
            groups[g].append({"match": match, "prediction": pred_map.get(match.pk)})

        all_team_ids = {m.home_team_id for m in all_matches} | {m.away_team_id for m in all_matches}
        team_map = {t.pk: t for t in Team.objects.filter(pk__in=all_team_ids)}

        group_data = []
        for letter in sorted(groups.keys()):
            group_standings = get_predicted_group_standings(user, self.pool, letter)
            enriched = [(s, team_map.get(s.team_id)) for s in group_standings]
            group_data.append(
                {"letter": letter, "matches": groups[letter], "standings": enriched}
            )

        ctx["pool"] = self.pool
        ctx["group_data"] = group_data
        ctx["predictions_submitted"] = self.membership.predictions_submitted
        ctx["total_predicted"] = len(pred_map)
        ctx["total_matches"] = all_matches.count()
        return ctx


class SaveMatchPredictionView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pool_id: int, match_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        pool = get_object_or_404(Pool, pk=pool_id)
        membership = get_object_or_404(PoolMembership, pool=pool, user=user)

        if membership.predictions_submitted:
            return HttpResponse("Predicciones ya enviadas.", status=403)

        match = get_object_or_404(Match, pk=match_id, tournament=pool.tournament)

        form = MatchPredictionForm(request.POST)
        if not form.is_valid():
            return HttpResponse("Datos inválidos.", status=400)

        Prediction.objects.update_or_create(
            user=user,
            pool=pool,
            match=match,
            defaults={
                "predicted_home_score": form.cleaned_data["predicted_home_score"],
                "predicted_away_score": form.cleaned_data["predicted_away_score"],
            },
        )

        standings = get_predicted_group_standings(user, pool, match.group_letter)
        team_ids = [s.team_id for s in standings]
        team_map = {t.pk: t for t in Team.objects.filter(pk__in=team_ids)}
        enriched = [(s, team_map.get(s.team_id)) for s in standings]
        return render(
            request,
            "predictions/partials/group_standings.html",
            {"standings": enriched, "group_letter": match.group_letter},
        )
