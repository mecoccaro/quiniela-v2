from django.contrib import admin
from django.db.models import Count

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


@admin.action(description="Lock selected pools")
def lock_pools(modeladmin, request, queryset):
    queryset.update(status=Pool.Status.LOCKED)


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ["name", "tournament", "status", "member_count", "lock_deadline"]
    list_filter = ["status", "tournament"]
    inlines = [PoolMembershipInline]
    actions = [lock_pools]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_member_count=Count("memberships"))

    @admin.display(ordering="_member_count", description="Members")
    def member_count(self, obj: Pool) -> int:
        return obj._member_count  # type: ignore[attr-defined]


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
