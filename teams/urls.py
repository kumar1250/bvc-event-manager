from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Public
    path("register/", views.register_team),
    path("check-name/<str:team_name>/", views.check_team_name),
    path("problems/", views.list_problems_public),          # <-- new
    path("site-content/", views.site_content_public),        # <-- new: dynamic Home page content

    # Team leader (roll-number token, not Django/JWT auth)             <-- new
    path("team/login/", views.team_login),
    path("team/me/", views.team_me),
    path("team/choose-problem/", views.team_choose_problem),
    path("team/save-idea/", views.team_save_idea),

    # Admin auth
    path("admin/login/", views.admin_login),
    path("admin/token/refresh/", TokenRefreshView.as_view()),

    # Admin (JWT protected)
    path("admin/teams/", views.list_teams),
    path("admin/teams/<int:team_id>/", views.delete_team),
    path("admin/dashboard/", views.dashboard),
    path("admin/download/", views.download_teams),

    # Admin (JWT protected) — Problem statements CRUD          <-- new
    path("admin/problems/", views.admin_problems),             # GET (list), POST (create)
    path("admin/problems/<int:problem_id>/", views.admin_problem_detail),  # GET/PUT/PATCH/DELETE

    path("admin/problems/download/", views.download_problems), # <-- new
    

    path("admin/problems/visibility/", views.admin_problems_visibility),  # <-- new: GET/PATCH

    # Admin (JWT protected) — Site content (Home page + coordinators)   <-- new
    path("admin/site-content/", views.admin_site_content),   # GET / PUT / PATCH

    # Public — Dynamic Forms (Google-Forms-style, admin-built)          <-- new
    path("forms/<int:form_id>/", views.public_form_detail),            # GET schema
    path("forms/<int:form_id>/submit/", views.public_form_submit),     # POST answers

    # Admin (JWT protected) — Dynamic Forms CRUD + responses            <-- new
    path("admin/forms/", views.admin_forms),                                    # GET (list), POST (create)
    path("admin/forms/<int:form_id>/", views.admin_form_detail),                # GET/PUT/PATCH/DELETE
    path("admin/forms/<int:form_id>/responses/", views.admin_form_responses),   # GET
    path("admin/forms/<int:form_id>/responses/<int:response_id>/", views.admin_delete_response),  # DELETE
    path("admin/forms/<int:form_id>/responses/download/", views.admin_download_form_responses),   # GET xlsx
]