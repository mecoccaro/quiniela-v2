from django import forms
from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse

from .models import Match, Team, Tournament, TournamentTeam


class ScoreFinalPicksForm(forms.Form):
    official_champion = forms.ModelChoiceField(queryset=Team.objects.all(), label="Official Champion")
    official_top_scorer_name = forms.CharField(max_length=100, label="Official Top Scorer Name")


_SCORING_HELP = (
    "Leave empty to use the built-in defaults. "
    "Paste a full JSON object to override, e.g.:<br><pre>"
    '{\n  "group":       {"exact_score": 3, "correct_result": 5},\n'
    '  "r32":         {"exact_score": 4, "correct_result": 6, "pens_winner": 1, "correct_slot": 2},\n'
    '  "r16":         {"exact_score": 5, "correct_result": 7, "pens_winner": 1, "correct_slot": 3},\n'
    '  "qf":          {"exact_score": 6, "correct_result": 8, "pens_winner": 1, "correct_slot": 4},\n'
    '  "sf":          {"exact_score": 7, "correct_result": 9, "pens_winner": 1, "correct_slot": 5},\n'
    '  "third_place": {"exact_score": 5, "correct_result": 7, "pens_winner": 1, "correct_slot": 3},\n'
    '  "final":       {"exact_score": 10, "correct_result": 12, "pens_winner": 2, "correct_slot": 6},\n'
    '  "champion":    10,\n'
    '  "top_scorer":  5\n}'
    "</pre>"
)


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "status", "num_groups"]
    prepopulated_fields = {"slug": ("name",)}
    actions = ["score_final_picks_action"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "status", "num_groups", "teams_per_group", "third_place_advancers"]}),
        ("Scoring config", {
            "fields": ["scoring_config"],
            "description": _SCORING_HELP,
            "classes": ["collapse"],
        }),
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:tournament_id>/score-final-picks/",
                self.admin_site.admin_view(self.score_final_picks_view),
                name="tournaments_tournament_score_final_picks",
            ),
        ]
        return custom + urls

    @admin.action(description="Score final picks (champion + top scorer)")
    def score_final_picks_action(self, request: HttpRequest, queryset) -> HttpResponse | None:
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one tournament.", level=messages.ERROR)
            return None
        tournament = queryset.first()
        return HttpResponseRedirect(
            reverse("admin:tournaments_tournament_score_final_picks", args=[tournament.pk])
        )

    def score_final_picks_view(self, request: HttpRequest, tournament_id: int) -> HttpResponse:
        tournament = get_object_or_404(Tournament, pk=tournament_id)
        if request.method == "POST":
            form = ScoreFinalPicksForm(request.POST)
            if form.is_valid():
                champion = form.cleaned_data["official_champion"]
                top_scorer = form.cleaned_data["official_top_scorer_name"]
                try:
                    from apps.leaderboard.tasks import score_final_picks  # noqa: PLC0415
                    score_final_picks.delay(tournament_id, champion.pk, top_scorer)
                    self.message_user(request, "Scoring task queued successfully.")
                except ImportError:
                    self.message_user(
                        request, "Leaderboard tasks not yet available.", level=messages.WARNING
                    )
                return HttpResponseRedirect(reverse("admin:tournaments_tournament_changelist"))
        else:
            form = ScoreFinalPicksForm()

        context = {
            **self.admin_site.each_context(request),
            "title": f"Score Final Picks — {tournament}",
            "form": form,
            "tournament": tournament,
            "opts": self.model._meta,
        }
        return render(request, "admin/tournaments/score_final_picks.html", context)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "fifa_code"]
    search_fields = ["name", "fifa_code"]


@admin.register(TournamentTeam)
class TournamentTeamAdmin(admin.ModelAdmin):
    list_display = ["tournament", "team", "group_letter", "fifa_ranking"]
    list_filter = ["tournament", "group_letter"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["tournament", "stage", "group_letter", "home_team", "away_team", "status", "home_score", "away_score"]
    list_filter = ["tournament", "stage", "status", "group_letter"]
    search_fields = ["home_team__name", "away_team__name"]

    def save_model(self, request: HttpRequest, obj: Match, form, change: bool) -> None:
        # The post_save signal on Match already triggers recalculate_pool_scores,
        # so no explicit call needed here — calling it twice would wipe previous_rank.
        super().save_model(request, obj, form, change)
