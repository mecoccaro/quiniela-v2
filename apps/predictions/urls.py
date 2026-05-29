from django.urls import path

from . import views

urlpatterns = [
    path(
        "pool/<int:pool_id>/group-stage/",
        views.GroupPredictionsView.as_view(),
        name="group_predictions",
    ),
    path(
        "pool/<int:pool_id>/match/<int:match_id>/",
        views.SaveMatchPredictionView.as_view(),
        name="save_match_prediction",
    ),
    path(
        "pool/<int:pool_id>/knockout/",
        views.KnockoutPredictionsView.as_view(),
        name="knockout_predictions",
    ),
    path(
        "pool/<int:pool_id>/third-place-tiebreaker/",
        views.ThirdPlaceTiebreakerView.as_view(),
        name="third_place_tiebreaker",
    ),
    path(
        "pool/<int:pool_id>/knockout/match/<int:match_id>/",
        views.SaveKnockoutPredictionView.as_view(),
        name="save_knockout_prediction",
    ),
    path(
        "pool/<int:pool_id>/picks/",
        views.PicksView.as_view(),
        name="picks",
    ),
    path(
        "pool/<int:pool_id>/picks/champion/",
        views.SaveChampionPickView.as_view(),
        name="save_champion_pick",
    ),
    path(
        "pool/<int:pool_id>/picks/top-scorer/",
        views.SaveTopScorerPickView.as_view(),
        name="save_top_scorer_pick",
    ),
    path(
        "pool/<int:pool_id>/submit/",
        views.SubmitPredictionsView.as_view(),
        name="submit_predictions",
    ),
]
