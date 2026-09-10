from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        REGISTRATION_SUCCESS = "registration_success", "Registration Successful"
        EVENT_UPDATED = "event_updated", "Event Updated"
        EVENT_CANCELLED = "event_cancelled", "Event Cancelled"
        REGISTRATION_CLOSING = "registration_closing", "Registration Closing Soon"
        GENERAL = "general", "General"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=30, choices=Type.choices, default=Type.GENERAL)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} -> {self.user.email}"


class EmailLog(models.Model):
    """Lightweight audit trail of outbound emails sent through Brevo."""

    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    template = models.CharField(max_length=50)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.template} -> {self.to_email} ({'ok' if self.success else 'failed'})"
