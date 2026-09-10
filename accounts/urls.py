from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view()),
    path("login/", views.LoginView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("me/", views.MeView.as_view()),
    path("change-password/", views.ChangePasswordView.as_view()),
    path("forgot-password/", views.ForgotPasswordView.as_view()),
    path("reset-password/", views.ResetPasswordView.as_view()),

    # Admin user management
    path("admin/users/", views.AdminUserListView.as_view()),
    path("admin/users/<int:pk>/", views.AdminUserDetailView.as_view()),
    path("admin/users/<int:pk>/reset-password/", views.AdminResetUserPasswordView.as_view()),
]
