from rest_framework import serializers

from .models import FieldOption, FormAnswer, FormField, FormSubmission, RegistrationForm


class FieldOptionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = FieldOption
        fields = ["id", "label", "value", "order"]


class FormFieldSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    options = FieldOptionSerializer(many=True, required=False)
    # Plain integer, not a PrimaryKeyRelatedField: in builder-save payloads this
    # refers to another field's *client-supplied* temp `id` within the same
    # payload (which may not exist as a real FormField pk yet), resolved by
    # FormBuilderSaveSerializer.save() after all fields are created.
    depends_on_field = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = FormField
        fields = [
            "id", "label", "field_type", "placeholder", "description", "required",
            "default_value", "min_length", "max_length", "min_value", "max_value",
            "validation_regex", "order", "options", "depends_on_field", "depends_on_value",
        ]


class FormFieldReadSerializer(serializers.ModelSerializer):
    """Read-only variant used for schema output (public form render + builder GET).
    depends_on_field is exposed as the plain integer id of the parent field."""

    options = FieldOptionSerializer(many=True, read_only=True)
    depends_on_field = serializers.IntegerField(source="depends_on_field_id", read_only=True, allow_null=True)

    class Meta:
        model = FormField
        fields = [
            "id", "label", "field_type", "placeholder", "description", "required",
            "default_value", "min_length", "max_length", "min_value", "max_value",
            "validation_regex", "order", "options", "depends_on_field", "depends_on_value",
        ]


class RegistrationFormSerializer(serializers.ModelSerializer):
    """Full schema, used for admin builder view and public form rendering."""

    fields = FormFieldReadSerializer(many=True, read_only=True)
    event_name = serializers.CharField(source="event.name", read_only=True)

    class Meta:
        model = RegistrationForm
        fields = ["id", "event", "event_name", "title", "description", "status", "fields", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class RegistrationFormListSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source="event.name", read_only=True)
    field_count = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = RegistrationForm
        fields = ["id", "event", "event_name", "title", "status", "field_count", "submission_count", "updated_at"]

    def get_field_count(self, obj):
        return obj.fields.count()

    def get_submission_count(self, obj):
        return obj.submissions.count()


class RegistrationFormWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistrationForm
        fields = ["id", "event", "title", "description", "status"]


class FormBuilderSaveSerializer(serializers.Serializer):
    """Accepts the full list of fields (with nested options) and replaces the form's field set."""

    title = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    fields = FormFieldSerializer(many=True)

    def save(self, form: RegistrationForm):
        validated = self.validated_data
        if "title" in validated:
            form.title = validated["title"]
        if "description" in validated:
            form.description = validated["description"]
        form.save()

        # Full replace: simplest reliable approach for a drag-and-drop builder.
        form.fields.all().delete()
        id_map = {}  # client-supplied temp id/index -> real FormField
        fields_data = validated["fields"]

        created_fields = []
        for index, field_data in enumerate(fields_data):
            options_data = field_data.pop("options", [])
            client_id = field_data.pop("id", None)
            depends_on_field = field_data.pop("depends_on_field", None)
            field_data.pop("depends_on_value", None)
            field = FormField.objects.create(
                form=form, order=field_data.pop("order", index), **field_data
            )
            for opt_index, opt in enumerate(options_data):
                opt.pop("id", None)
                FieldOption.objects.create(field=field, order=opt.get("order", opt_index), **{
                    k: v for k, v in opt.items() if k != "order"
                })
            created_fields.append((field, client_id, depends_on_field))
            if client_id is not None:
                id_map[client_id] = field

        # Second pass: wire up conditional-logic references (depends_on_field
        # may point to a field defined earlier or later in the same payload).
        for field, client_id, depends_on_field in created_fields:
            if depends_on_field is not None:
                target = id_map.get(depends_on_field) or id_map.get(getattr(depends_on_field, "id", None))
                if target:
                    field.depends_on_field = target
                    field.save(update_fields=["depends_on_field"])

        return form


class FormAnswerSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(source="field.label", read_only=True)
    field_type = serializers.CharField(source="field.field_type", read_only=True)

    class Meta:
        model = FormAnswer
        fields = ["field", "field_label", "field_type", "value"]


class FormSubmissionListSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source="event.name", read_only=True)
    form_title = serializers.CharField(source="form.title", read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = FormSubmission
        fields = [
            "id", "registration_id", "event", "event_name", "form", "form_title",
            "name", "email", "status", "submitted_at",
        ]

    def get_name(self, obj):
        return (
            obj.get_answer_value_for_label("Full Name")
            or obj.get_answer_value_for_label("Name")
            or (obj.user.full_name if obj.user else "")
        )

    def get_email(self, obj):
        return obj.get_answer_value_for_label("Email") or (obj.user.email if obj.user else "")


class FormSubmissionDetailSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source="event.name", read_only=True)
    form_title = serializers.CharField(source="form.title", read_only=True)
    answers = FormAnswerSerializer(many=True, read_only=True)
    answers_dict = serializers.SerializerMethodField()

    class Meta:
        model = FormSubmission
        fields = [
            "id", "registration_id", "event", "event_name", "form", "form_title",
            "status", "submitted_at", "updated_at", "answers", "answers_dict",
        ]

    def get_answers_dict(self, obj):
        return obj.as_dict()
