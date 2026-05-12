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
]
