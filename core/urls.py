from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Legacy single-hackathon app (kept as-is; do not break it).
    # NOTE: this already owns paths like api/forms/<id>/submit/, so the new
    # multi-event platform below is namespaced under api/v2/ to avoid clashing.
    path("api/", include("teams.urls")),

    # Dynamic Event Management Platform (new)
    path("api/v2/auth/", include("accounts.urls")),
    path("api/v2/events/", include("events.urls")),
    path("api/v2/coordinators/", include("coordinators.urls")),
    path("api/v2/forms/", include("forms.urls")),
    path("api/v2/registrations/", include("forms.registrations_urls")),
    path("api/v2/notifications/", include("notifications.urls")),
    path("api/v2/dashboard/", include("dashboardapi.urls")),
]
