from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from apps.pools.models import LeaderboardEntry, PoolMembership

from .forms import RegistrationForm
from .models import User


class RegisterView(CreateView):
    model = User
    form_class = RegistrationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "users/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        memberships = list(
            PoolMembership.objects.filter(user=self.request.user)
            .select_related("pool", "pool__tournament")
            .order_by("pool__name")
        )
        pool_ids = [m.pool_id for m in memberships]
        rank_map = {
            e.pool_id: e.rank
            for e in LeaderboardEntry.objects.filter(
                user=self.request.user, pool_id__in=pool_ids
            )
        }
        ctx["membership_data"] = [
            (m, rank_map.get(m.pool_id)) for m in memberships
        ]
        return ctx
