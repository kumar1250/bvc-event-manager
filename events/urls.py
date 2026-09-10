from django.urls import path
from . import views

urlpatterns = [
    # Public
    path("", views.EventListView.as_view()),
    path("<str:pk>/", views.EventDetailView.as_view()),

    # Admin CRUD
    path("admin/list/", views.AdminEventListCreateView.as_view()),
    path("admin/<int:pk>/", views.AdminEventDetailView.as_view()),
    path("admin/<int:pk>/cancel/", views.CancelEventView.as_view()),

    # Event flow (admin + coordinator)
    path("<int:event_id>/flow/", views.EventFlowListCreateView.as_view()),
    path("<int:event_id>/flow/<int:pk>/", views.EventFlowDetailView.as_view()),
    path("<int:event_id>/flow/reorder/", views.EventFlowReorderView.as_view()),
]
