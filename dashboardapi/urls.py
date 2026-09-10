from django.urls import path
from . import views

urlpatterns = [
    path("stats/", views.AdminDashboardStatsView.as_view()),
    path("me/", views.MyDashboardView.as_view()),
]
