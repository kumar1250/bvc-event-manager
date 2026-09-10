"""Separate url module mounted at /api/registrations/ - cross-event registration management."""
from django.urls import path
from . import views

urlpatterns = [
    path("", views.AdminRegistrationListView.as_view()),
    path("export/", views.ExportAllRegistrationsView.as_view()),
    path("export/event/<int:event_id>/", views.ExportEventRegistrationsView.as_view()),
    path("mine/", views.MyRegistrationsView.as_view()),
    path("mine/<int:pk>/", views.MyRegistrationDetailView.as_view()),
]
