from django.contrib import admin

from .models import Match, Team, Tournament, TournamentTeam


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "status", "num_groups"]
    prepopulated_fields = {"slug": ("name",)}


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
