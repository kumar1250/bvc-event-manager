from django.urls import path
from . import views

urlpatterns = [
    # Public
    path("<int:pk>/", views.PublicFormDetailView.as_view()),
    path("<int:pk>/submit/", views.PublicFormSubmitView.as_view()),

    # Admin/coordinator: forms CRUD + builder + status
    path("admin/list/", views.AdminFormListCreateView.as_view()),
    path("admin/<int:pk>/", views.AdminFormDetailView.as_view()),
    path("admin/<int:pk>/builder/", views.FormBuilderView.as_view()),
    path("admin/<int:pk>/status/", views.FormStatusView.as_view()),

    # Admin/coordinator: responses for one form
    path("admin/<int:pk>/responses/", views.AdminFormResponsesView.as_view()),
    path("admin/<int:pk>/responses/export/", views.ExportFormResponsesView.as_view()),

    # Submission detail / moderation
    path("submissions/<int:pk>/", views.SubmissionDetailView.as_view()),
    path("submissions/<int:pk>/status/", views.SubmissionStatusView.as_view()),
]
