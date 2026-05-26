from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("users/", include("apps.users.urls")),
    path("predictions/", include("apps.predictions.urls")),
    path("", include("apps.leaderboard.urls")),
    path("", RedirectView.as_view(pattern_name="dashboard", permanent=False)),
]
