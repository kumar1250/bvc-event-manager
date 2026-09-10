from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User
from events.models import Event

from .models import Coordinator


class CoordinatorPublicSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name")

    class Meta:
        model = Coordinator
        fields = ["id", "name", "department", "designation", "profile_image_url", "bio"]


class CoordinatorSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name")
    email = serializers.EmailField(source="user.email")
    phone = serializers.CharField(source="user.phone", required=False)
    assigned_events = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Event.objects.all(), required=False
    )

    class Meta:
        model = Coordinator
        fields = [
            "id", "name", "email", "phone", "department", "designation",
            "profile_image_url", "bio", "assigned_events", "is_active", "created_at",
        ]
        read_only_fields = ["created_at"]


class CoordinatorCreateSerializer(serializers.Serializer):
    """Creates a User (role=coordinator) + Coordinator profile together, and emails a temp password."""

    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    department = serializers.CharField(max_length=150, required=False, allow_blank=True)
    designation = serializers.CharField(max_length=150, required=False, allow_blank=True)
    profile_image_url = serializers.URLField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    assigned_events = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Event.objects.all(), required=False
    )
    password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        events = validated_data.pop("assigned_events", [])
        password = validated_data.pop("password")
        email = validated_data.pop("email")
        user = User(
            email=email, username=email, full_name=validated_data.pop("name"),
            phone=validated_data.get("phone", ""), role=User.Role.COORDINATOR,
        )
        user.set_password(password)
        user.save()
        coordinator = Coordinator.objects.create(
            user=user,
            department=validated_data.get("department", ""),
            designation=validated_data.get("designation", ""),
            profile_image_url=validated_data.get("profile_image_url", ""),
            bio=validated_data.get("bio", ""),
        )
        if events:
            coordinator.assigned_events.set(events)
        return coordinator
