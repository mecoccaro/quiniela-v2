from django.contrib import admin

from .models import (
    LeaderboardEntry,
    Pool,
    PoolChampionPick,
    PoolMembership,
    PoolTopScorerPick,
    Prediction,
)


class PoolMembershipInline(admin.TabularInline):
    model = PoolMembership
    extra = 1
    fields = ["user", "predictions_submitted", "joined_at"]
    readonly_fields = ["joined_at"]


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ["name", "tournament", "status", "lock_deadline"]
    list_filter = ["status", "tournament"]
    inlines = [PoolMembershipInline]


@admin.register(PoolMembership)
class PoolMembershipAdmin(admin.ModelAdmin):
    list_display = ["pool", "user", "predictions_submitted", "joined_at"]
    list_filter = ["pool", "predictions_submitted"]


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ["user", "pool", "match", "predicted_home_score", "predicted_away_score", "points_awarded"]
    list_filter = ["pool", "user"]
    search_fields = ["user__nickname", "match__home_team__name"]
    readonly_fields = [
        "user", "pool", "match", "predicted_home_score", "predicted_away_score",
        "predicted_winner", "points_awarded",
    ]

    def has_add_permission(self, request):        return False


@admin.register(PoolChampionPick)
class PoolChampionPickAdmin(admin.ModelAdmin):
    list_display = ["user", "pool", "team", "points_awarded"]
    readonly_fields = ["user", "pool", "team", "points_awarded"]

    def has_add_permission(self, request):        return False


@admin.register(PoolTopScorerPick)
class PoolTopScorerPickAdmin(admin.ModelAdmin):
    list_display = ["user", "pool", "player_name", "points_awarded"]
    readonly_fields = ["user", "pool", "player_name", "points_awarded"]

    def has_add_permission(self, request):        return False


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ["pool", "user", "rank", "total_points", "last_calculated_at"]
    list_filter = ["pool"]
    readonly_fields = ["pool", "user", "rank", "total_points", "last_calculated_at"]
