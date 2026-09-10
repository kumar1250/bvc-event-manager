from rest_framework import serializers

from .models import Event, EventFlowStep


class EventFlowStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventFlowStep
        fields = ["id", "title", "description", "date", "time", "order", "status"]


class CoordinatorMiniSerializer(serializers.Serializer):
    """Lightweight coordinator info embedded in event responses (avoids app import cycle)."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    department = serializers.CharField()
    designation = serializers.CharField()
    profile_image_url = serializers.CharField()


class EventListSerializer(serializers.ModelSerializer):
    registration_count = serializers.ReadOnlyField()
    seats_remaining = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    is_registration_open = serializers.ReadOnlyField()

    class Meta:
        model = Event
        fields = [
            "id", "name", "slug", "category", "banner_image_url", "date", "start_time",
            "end_time", "venue", "status", "max_participants", "registration_count",
            "seats_remaining", "is_full", "is_registration_open",
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    flow_steps = EventFlowStepSerializer(many=True, read_only=True)
    registration_count = serializers.ReadOnlyField()
    seats_remaining = serializers.ReadOnlyField()
    is_full = serializers.ReadOnlyField()
    is_registration_open = serializers.ReadOnlyField()
    coordinators = serializers.SerializerMethodField()
    active_form_id = serializers.SerializerMethodField()
    active_forms = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id", "name", "slug", "description", "category", "banner_image_url",
            "date", "start_time", "end_time", "venue", "registration_start",
            "registration_end", "max_participants", "status", "instructions",
            "flow_steps", "coordinators", "registration_count", "seats_remaining",
            "is_full", "is_registration_open", "active_form_id", "active_forms",
            "created_at", "updated_at",
        ]

    def get_coordinators(self, obj):
        return [
            {
                "id": c.id,
                "name": c.user.full_name,
                "department": c.department,
                "designation": c.designation,
                "profile_image_url": c.profile_image_url,
                "bio": c.bio,
            }
            for c in obj.assigned_coordinators.filter(is_active=True)
        ]

    def get_active_form_id(self, obj):
        form = obj.forms.filter(status="active").order_by("-id").first()
        return form.id if form else None

    def get_active_forms(self, obj):
        # An event can run several forms at once (e.g. separate "activities" -
        # a drawing competition, a quiz, ...). Each is returned collapsed
        # (title + description only); the frontend loads the full field
        # schema for one via GET /forms/<id>/ only once the person opens it.
        return [
            {"id": f.id, "title": f.title, "description": f.description}
            for f in obj.forms.filter(status="active").order_by("id")
        ]


class EventWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id", "name", "description", "category", "banner_image_url",
            "date", "start_time", "end_time", "venue", "registration_start",
            "registration_end", "max_participants", "status", "instructions",
        ]
