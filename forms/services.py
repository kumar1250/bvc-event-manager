import json
import re

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from .models import FieldOption, FormAnswer, FormField, FormSubmission


def _condition_met(field: FormField, answers_by_field_id: dict) -> bool:
    """Whether a conditional field's dependency is satisfied by the answers given so far."""
    if not field.depends_on_field_id:
        return True
    parent_value = answers_by_field_id.get(field.depends_on_field_id)
    if parent_value is None:
        return False
    if isinstance(parent_value, list):
        return field.depends_on_value in parent_value
    return str(parent_value) == str(field.depends_on_value)


def _validate_single_value(field: FormField, value):
    ftype = field.field_type

    if ftype == FormField.FieldType.EMAIL:
        try:
            validate_email(value)
        except DjangoValidationError:
            raise ValidationError({field.label: "Enter a valid email address."})

    if ftype == FormField.FieldType.PHONE:
        if not re.match(r"^[0-9+\-\s()]{7,20}$", str(value)):
            raise ValidationError({field.label: "Enter a valid phone number."})

    if ftype == FormField.FieldType.NUMBER:
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ValidationError({field.label: "Must be a number."})
        if field.min_value is not None and num < field.min_value:
            raise ValidationError({field.label: f"Must be at least {field.min_value}."})
        if field.max_value is not None and num > field.max_value:
            raise ValidationError({field.label: f"Must be at most {field.max_value}."})

    if ftype == FormField.FieldType.URL:
        if not re.match(r"^https?://", str(value)):
            raise ValidationError({field.label: "Enter a valid URL (starting with http:// or https://)."})

    if ftype in (FormField.FieldType.SHORT_TEXT, FormField.FieldType.LONG_TEXT, FormField.FieldType.ADDRESS):
        if field.min_length and len(str(value)) < field.min_length:
            raise ValidationError({field.label: f"Must be at least {field.min_length} characters."})
        if field.max_length and len(str(value)) > field.max_length:
            raise ValidationError({field.label: f"Must be at most {field.max_length} characters."})

    if field.validation_regex:
        if not re.match(field.validation_regex, str(value)):
            raise ValidationError({field.label: "Invalid format."})

    if field.has_options:
        valid_values = set(field.options.values_list("value", flat=True))
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v not in valid_values:
                raise ValidationError({field.label: f"'{v}' is not a valid option."})


def validate_and_normalize_answers(form, raw_answers: dict) -> dict:
    """
    raw_answers: {field_id (str or int): value}
    Returns: {field_id: normalized_value} ready to persist, having applied
    required + type + conditional-logic validation.
    Raises rest_framework.exceptions.ValidationError on any problem.
    """
    fields = list(form.fields.select_related("depends_on_field").prefetch_related("options"))
    answers_by_id = {}
    for f in fields:
        key = str(f.id)
        if key in raw_answers:
            answers_by_id[f.id] = raw_answers[key]

    errors = {}
    normalized = {}

    for field in fields:
        if not field.is_input:
            continue

        condition_ok = _condition_met(field, answers_by_id)
        value = answers_by_id.get(field.id)
        is_empty = value is None or value == "" or value == []

        if not condition_ok:
            continue  # hidden field: skip entirely, don't require or store

        if field.required and is_empty:
            errors[field.label] = "This field is required."
            continue

        if is_empty:
            continue

        try:
            _validate_single_value(field, value)
        except ValidationError as exc:
            errors.update(exc.detail if isinstance(exc.detail, dict) else {field.label: str(exc.detail)})
            continue

        normalized[field.id] = value

    if errors:
        raise ValidationError(errors)

    return normalized


def create_submission(form, event, user, raw_answers: dict) -> FormSubmission:
    normalized = validate_and_normalize_answers(form, raw_answers)

    if event.max_participants is not None and event.registration_count >= event.max_participants:
        raise ValidationError({"detail": "Registration is full for this event."})

    submission = FormSubmission.objects.create(form=form, event=event, user=user)
    answers = []
    for field_id, value in normalized.items():
        stored_value = json.dumps(value) if isinstance(value, list) else str(value)
        answers.append(FormAnswer(submission=submission, field_id=field_id, value=stored_value))
    FormAnswer.objects.bulk_create(answers)
    return submission
