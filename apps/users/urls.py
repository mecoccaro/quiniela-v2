from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "login/",
        LoginView.as_view(template_name="users/login.html"),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("password-recovery/", views.PasswordRecoveryView.as_view(), name="password_recovery"),
    path("password-recovery/set/", views.SetNewPasswordView.as_view(), name="set_new_password"),
]
