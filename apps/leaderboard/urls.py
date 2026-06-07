from django.urls import path

from . import views

urlpatterns = [
    path("pool/<int:pool_id>/leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("pool/<int:pool_id>/my-predictions/", views.MyPredictionsView.as_view(), name="my_predictions"),
    path("pool/<int:pool_id>/participants/", views.ParticipantsView.as_view(), name="participants"),
    path("pool/<int:pool_id>/day/", views.PoolDayView.as_view(), name="pool_day"),
    path("pool/<int:pool_id>/scoring-guide/", views.ScoringGuideView.as_view(), name="scoring_guide"),
]
