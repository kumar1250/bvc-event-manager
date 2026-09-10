import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Custom user model. Email is the login identifier."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        COORDINATOR = "coordinator", "Coordinator"
        USER = "user", "User"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_active_account = models.BooleanField(default=True)
    profile_image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.full_name or self.username} <{self.email}>"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_coordinator(self):
        return self.role == self.Role.COORDINATOR


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return (not self.used) and timezone.now() <= self.expires_at

    def __str__(self):
        return f"Reset token for {self.user.email}"
