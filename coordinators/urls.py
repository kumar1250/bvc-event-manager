from django.urls import path
from . import views

urlpatterns = [
    path("", views.PublicCoordinatorListView.as_view()),
    path("admin/list/", views.AdminCoordinatorListCreateView.as_view()),
    path("admin/<int:pk>/", views.AdminCoordinatorDetailView.as_view()),
    path("admin/<int:pk>/toggle-active/", views.ToggleCoordinatorActiveView.as_view()),

    path("me/events/", views.MyCoordinatorEventsView.as_view()),
    path("me/dashboard/", views.MyCoordinatorDashboardView.as_view()),
]
