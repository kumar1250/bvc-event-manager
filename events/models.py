from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Event(models.Model):
    class Category(models.TextChoices):
        TECHNICAL = "technical", "Technical"
        CULTURAL = "cultural", "Cultural"
        SPORTS = "sports", "Sports"
        LITERARY = "literary", "Literary"
        WORKSHOP = "workshop", "Workshop"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        UPCOMING = "upcoming", "Upcoming"
        REGISTRATION_OPEN = "registration_open", "Registration Open"
        REGISTRATION_CLOSED = "registration_closed", "Registration Closed"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    banner_image_url = models.URLField(blank=True)

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=255, blank=True)

    registration_start = models.DateTimeField(null=True, blank=True)
    registration_end = models.DateTimeField(null=True, blank=True)
    max_participants = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    instructions = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-start_time"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:200]
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def registration_count(self):
        return self.submissions.filter(status__in=["pending", "approved"]).count()

    @property
    def seats_remaining(self):
        if self.max_participants is None:
            return None
        return max(self.max_participants - self.registration_count, 0)

    @property
    def is_full(self):
        return self.max_participants is not None and self.registration_count >= self.max_participants

    @property
    def is_registration_open(self):
        from django.utils import timezone
        if self.status != self.Status.REGISTRATION_OPEN:
            return False
        if self.is_full:
            return False
        now = timezone.now()
        if self.registration_start and now < self.registration_start:
            return False
        if self.registration_end and now > self.registration_end:
            return False
        return True


class EventFlowStep(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="flow_steps")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.event.name} - {self.title}"
