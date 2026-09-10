from django.conf import settings
from django.db import models

from events.models import Event


class Coordinator(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coordinator_profile"
    )
    department = models.CharField(max_length=150, blank=True)
    designation = models.CharField(max_length=150, blank=True)
    profile_image_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    assigned_events = models.ManyToManyField(
        Event, blank=True, related_name="assigned_coordinators"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.full_name or self.user.email
