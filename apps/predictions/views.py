from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

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

from .forms import ChampionPickForm, KnockoutPredictionForm, MatchPredictionForm, TopScorerPickForm

STAGE_LABELS = {
    "r32": "Ronda de 32",
    "r16": "Octavos de final",
    "qf": "Cuartos de final",
    "sf": "Semifinales",
    "final": "Final",
}


# ─── Group Stage ──────────────────────────────────────────────────────────────

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


# ─── Knockout Stage ───────────────────────────────────────────────────────────

class KnockoutPredictionsView(LoginRequiredMixin, View):

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        pool = get_object_or_404(Pool, pk=kwargs["pool_id"])
        self.membership = get_object_or_404(PoolMembership, pool=pool, user=request.user)

        total_group = Match.objects.filter(
            tournament=pool.tournament, stage=Match.Stage.GROUP
        ).count()
        user_group = Prediction.objects.filter(
            user=request.user, pool=pool, match__stage=Match.Stage.GROUP
        ).count()
        if user_group < total_group:
            messages.warning(request, "Completá todas las predicciones de fase de grupos primero.")
            return redirect("group_predictions", pool_id=pool.pk)

        self.pool = pool
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        bracket = build_predicted_knockout_bracket(user, self.pool)
        stages = [
            {"key": k, "label": STAGE_LABELS[k], "slots": bracket.get(k, [])}
            for k in ("r32", "r16", "qf", "sf", "final")
            if k in bracket
        ]
        return render(request, "predictions/knockout.html", {
            "pool": self.pool,
            "stages": stages,
            "predictions_submitted": self.membership.predictions_submitted,
        })


class SaveKnockoutPredictionView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pool_id: int, match_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        pool = get_object_or_404(Pool, pk=pool_id)
        membership = get_object_or_404(PoolMembership, pool=pool, user=user)

        if membership.predictions_submitted:
            return HttpResponse("Predicciones ya enviadas.", status=403)

        match = get_object_or_404(Match, pk=match_id, tournament=pool.tournament)

        form = KnockoutPredictionForm(request.POST)
        if not form.is_valid():
            return HttpResponse(str(form.errors), status=400)

        winner_id = form.cleaned_data.get("predicted_winner")
        winner = get_object_or_404(Team, pk=winner_id) if winner_id else None

        Prediction.objects.update_or_create(
            user=user,
            pool=pool,
            match=match,
            defaults={
                "predicted_home_score": form.cleaned_data["predicted_home_score"],
                "predicted_away_score": form.cleaned_data["predicted_away_score"],
                "predicted_winner": winner,
            },
        )
        return HttpResponse(status=200)


# ─── Champion & Top Scorer Picks ──────────────────────────────────────────────

class PicksView(LoginRequiredMixin, View):

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        pool = get_object_or_404(Pool, pk=kwargs["pool_id"])
        self.membership = get_object_or_404(PoolMembership, pool=pool, user=request.user)
        self.pool = pool
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        bracket = build_predicted_knockout_bracket(user, self.pool)
        # Champion is derived from the Final prediction winner — not a free pick
        final_slots = bracket.get("final", [])
        predicted_champion: Team | None = None
        if final_slots and final_slots[0].prediction:
            pred = final_slots[0].prediction
            if pred.predicted_winner_id:
                predicted_champion = final_slots[0].home_team if pred.predicted_winner_id == (
                    final_slots[0].home_team.pk if final_slots[0].home_team else None
                ) else final_slots[0].away_team
            elif pred.predicted_home_score is not None and pred.predicted_away_score is not None:
                if pred.predicted_home_score > pred.predicted_away_score:
                    predicted_champion = final_slots[0].home_team
                elif pred.predicted_away_score > pred.predicted_home_score:
                    predicted_champion = final_slots[0].away_team
        top_scorer_pick = PoolTopScorerPick.objects.filter(user=user, pool=self.pool).first()
        return render(request, "predictions/picks.html", {
            "pool": self.pool,
            "predicted_champion": predicted_champion,
            "top_scorer_pick": top_scorer_pick,
            "predictions_submitted": self.membership.predictions_submitted,
        })


class SaveChampionPickView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        pool = get_object_or_404(Pool, pk=pool_id)
        membership = get_object_or_404(PoolMembership, pool=pool, user=user)

        if membership.predictions_submitted:
            return HttpResponse("Predicciones ya enviadas.", status=403)

        form = ChampionPickForm(request.POST)
        if not form.is_valid():
            return HttpResponse("Datos inválidos.", status=400)

        team = get_object_or_404(Team, pk=form.cleaned_data["team_id"])
        PoolChampionPick.objects.update_or_create(
            user=user, pool=pool, defaults={"team": team}
        )
        return HttpResponse(status=200)


class SaveTopScorerPickView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        pool = get_object_or_404(Pool, pk=pool_id)
        membership = get_object_or_404(PoolMembership, pool=pool, user=user)

        if membership.predictions_submitted:
            return HttpResponse("Predicciones ya enviadas.", status=403)

        form = TopScorerPickForm(request.POST)
        if not form.is_valid():
            return HttpResponse("Datos inválidos.", status=400)

        PoolTopScorerPick.objects.update_or_create(
            user=user, pool=pool, defaults={"player_name": form.cleaned_data["player_name"]}
        )
        return HttpResponse(status=200)


# ─── Submission ───────────────────────────────────────────────────────────────

class SubmitPredictionsView(LoginRequiredMixin, View):

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        pool = get_object_or_404(Pool, pk=kwargs["pool_id"])
        self.membership = get_object_or_404(PoolMembership, pool=pool, user=request.user)
        self.pool = pool
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        bracket = build_predicted_knockout_bracket(user, self.pool)
        final_slots = bracket.get("final", [])
        predicted_champion: Team | None = None
        if final_slots and final_slots[0].prediction:
            pred = final_slots[0].prediction
            if pred.predicted_winner_id:
                predicted_champion = final_slots[0].home_team if pred.predicted_winner_id == (
                    final_slots[0].home_team.pk if final_slots[0].home_team else None
                ) else final_slots[0].away_team
            elif pred.predicted_home_score is not None and pred.predicted_away_score is not None:
                if pred.predicted_home_score > pred.predicted_away_score:
                    predicted_champion = final_slots[0].home_team
                elif pred.predicted_away_score > pred.predicted_home_score:
                    predicted_champion = final_slots[0].away_team
        # If already submitted, fall back to stored champion pick
        if self.membership.predictions_submitted:
            stored = PoolChampionPick.objects.filter(user=user, pool=self.pool).first()
            if stored:
                predicted_champion = stored.team
        top_scorer_pick = PoolTopScorerPick.objects.filter(user=user, pool=self.pool).first()
        total_matches = Match.objects.filter(tournament=self.pool.tournament).count()
        user_predictions = Prediction.objects.filter(user=user, pool=self.pool).count()
        return render(request, "predictions/submission_confirm.html", {
            "pool": self.pool,
            "predicted_champion": predicted_champion,
            "top_scorer_pick": top_scorer_pick,
            "predictions_submitted": self.membership.predictions_submitted,
            "total_matches": total_matches,
            "user_predictions": user_predictions,
        })

    def post(self, request: HttpRequest, pool_id: int) -> HttpResponse:
        user: User = request.user  # type: ignore[assignment]
        if self.membership.predictions_submitted:
            return redirect("group_predictions", pool_id=self.pool.pk)

        # Require all matches to be predicted
        total_matches = Match.objects.filter(tournament=self.pool.tournament).count()
        user_predictions = Prediction.objects.filter(user=user, pool=self.pool).count()
        if user_predictions < total_matches:
            messages.error(
                request,
                f"Faltan predicciones: tenés {user_predictions} de {total_matches} partidos completados.",
            )
            return redirect("submit_predictions", pool_id=self.pool.pk)

        # Require top scorer pick
        if not PoolTopScorerPick.objects.filter(user=user, pool=self.pool).exists():
            messages.error(request, "Tenés que elegir un goleador antes de confirmar.")
            return redirect("picks", pool_id=self.pool.pk)

        # Auto-derive champion from Final prediction
        bracket = build_predicted_knockout_bracket(user, self.pool)
        final_slots = bracket.get("final", [])
        champion_team: Team | None = None
        if final_slots and final_slots[0].prediction:
            pred = final_slots[0].prediction
            if pred.predicted_winner_id:
                champion_team = final_slots[0].home_team if pred.predicted_winner_id == (
                    final_slots[0].home_team.pk if final_slots[0].home_team else None
                ) else final_slots[0].away_team
            elif pred.predicted_home_score is not None and pred.predicted_away_score is not None:
                if pred.predicted_home_score > pred.predicted_away_score:
                    champion_team = final_slots[0].home_team
                elif pred.predicted_away_score > pred.predicted_home_score:
                    champion_team = final_slots[0].away_team

        if champion_team:
            PoolChampionPick.objects.update_or_create(
                user=user, pool=self.pool, defaults={"team": champion_team}
            )

        self.membership.predictions_submitted = True
        self.membership.save()
        LeaderboardEntry.objects.get_or_create(
            pool=self.pool, user=user, defaults={"total_points": 0}
        )
        return redirect("group_predictions", pool_id=self.pool.pk)
