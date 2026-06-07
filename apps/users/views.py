from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView

from apps.pools.models import LeaderboardEntry, PoolMembership

from .forms import PasswordRecoveryForm, RegistrationForm, SetNewPasswordForm
from .models import User


class RegisterView(CreateView):
    model = User
    form_class = RegistrationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        invite_code = form.cleaned_data.get("invite_code")
        if invite_code:
            from apps.pools.models import Pool, PoolMembership
            pool = Pool.objects.filter(invite_code=invite_code).first()
            if pool:
                PoolMembership.objects.get_or_create(pool=pool, user=self.object)
        return response


class PasswordRecoveryView(FormView):
    template_name = "users/password_recovery.html"
    form_class = PasswordRecoveryForm

    def form_valid(self, form):
        try:
            user = User.objects.get(
                email=form.cleaned_data["email"],
                nickname=form.cleaned_data["nickname"],
            )
        except User.DoesNotExist:
            form.add_error(None, "No encontramos una cuenta con esos datos.")
            return self.form_invalid(form)
        self.request.session["password_recovery_user_id"] = user.pk
        return redirect("set_new_password")


class SetNewPasswordView(FormView):
    template_name = "users/set_password.html"
    form_class = SetNewPasswordForm
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if "password_recovery_user_id" not in request.session:
            return redirect("password_recovery")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = get_object_or_404(User, pk=self.request.session["password_recovery_user_id"])
        user.set_password(form.cleaned_data["password1"])
        user.save()
        del self.request.session["password_recovery_user_id"]
        login(self.request, user)
        return super().form_valid(form)


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
