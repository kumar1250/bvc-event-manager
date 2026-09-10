import random
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from events.models import Event


class RegistrationForm(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        CLOSED = "closed", "Closed"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="forms")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_forms"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.event.name})"

    @property
    def is_open(self):
        return self.status == self.Status.ACTIVE and self.event.is_registration_open


class FormField(models.Model):
    class FieldType(models.TextChoices):
        SHORT_TEXT = "short_text", "Short Text"
        LONG_TEXT = "long_text", "Long Text"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        NUMBER = "number", "Number"
        RADIO = "radio", "Radio"
        CHECKBOX = "checkbox", "Checkbox"
        DROPDOWN = "dropdown", "Dropdown"
        MULTISELECT = "multiselect", "Multi Select"
        DATE = "date", "Date"
        TIME = "time", "Time"
        DATETIME = "datetime", "Date & Time"
        URL = "url", "URL"
        ADDRESS = "address", "Address"
        IMAGE_URL = "image_url", "Image URL"
        FILE_UPLOAD = "file_upload", "File Upload"
        SECTION = "section", "Section"
        HEADING = "heading", "Heading"
        DESCRIPTION = "description", "Description"
        TERMS = "terms", "Terms & Conditions"

    NON_INPUT_TYPES = {FieldType.SECTION, FieldType.HEADING, FieldType.DESCRIPTION}
    OPTION_TYPES = {FieldType.RADIO, FieldType.CHECKBOX, FieldType.DROPDOWN, FieldType.MULTISELECT}

    form = models.ForeignKey(RegistrationForm, on_delete=models.CASCADE, related_name="fields")
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    placeholder = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    required = models.BooleanField(default=False)
    default_value = models.CharField(max_length=500, blank=True)

    min_length = models.PositiveIntegerField(null=True, blank=True)
    max_length = models.PositiveIntegerField(null=True, blank=True)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    validation_regex = models.CharField(max_length=500, blank=True)

    order = models.PositiveIntegerField(default=0)

    # Conditional logic: show this field only if `depends_on_field` has value `depends_on_value`.
    depends_on_field = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="dependents"
    )
    depends_on_value = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.label} ({self.field_type})"

    @property
    def is_input(self):
        return self.field_type not in self.NON_INPUT_TYPES

    @property
    def has_options(self):
        return self.field_type in self.OPTION_TYPES


class FieldOption(models.Model):
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if not self.value:
            self.value = self.label
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label


def _generate_registration_id():
    year = timezone.now().year
    suffix = "".join(random.choices(string.digits, k=5))
    return f"EVT-{year}-{suffix}"


class FormSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    form = models.ForeignKey(RegistrationForm, on_delete=models.CASCADE, related_name="submissions")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registrations",
    )
    registration_id = models.CharField(max_length=30, unique=True, editable=False)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]

    def save(self, *args, **kwargs):
        if not self.registration_id:
            reg_id = _generate_registration_id()
            while FormSubmission.objects.filter(registration_id=reg_id).exists():
                reg_id = _generate_registration_id()
            self.registration_id = reg_id
        super().save(*args, **kwargs)

    def __str__(self):
        return self.registration_id

    def get_answer_value_for_label(self, label):
        answer = self.answers.select_related("field").filter(field__label__iexact=label).first()
        return answer.value if answer else None

    def as_dict(self):
        """Ordered {label: value} of all submitted answers, for exports/detail views."""
        return {a.field.label: a.value for a in self.answers.select_related("field").order_by("field__order")}


class FormAnswer(models.Model):
    submission = models.ForeignKey(FormSubmission, on_delete=models.CASCADE, related_name="answers")
    field = models.ForeignKey(FormField, on_delete=models.CASCADE, related_name="answers")
    value = models.TextField(blank=True)  # JSON-encoded for multi-value fields (checkbox/multiselect)

    class Meta:
        unique_together = ("submission", "field")

    def __str__(self):
        return f"{self.field.label}: {self.value[:50]}"
