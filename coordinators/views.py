from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdmin
from events.models import Event
from events.serializers import EventListSerializer
from forms.models import FormSubmission

from .models import Coordinator
from .serializers import (
    CoordinatorCreateSerializer,
    CoordinatorPublicSerializer,
    CoordinatorSerializer,
)


class PublicCoordinatorListView(generics.ListAPIView):
    """Public: shown on the home / coordinators page."""

    serializer_class = CoordinatorPublicSerializer
    permission_classes = [AllowAny]
    queryset = Coordinator.objects.filter(is_active=True).select_related("user")


class AdminCoordinatorListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    queryset = Coordinator.objects.select_related("user").all()

    def get_serializer_class(self):
        return CoordinatorCreateSerializer if self.request.method == "POST" else CoordinatorSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        coordinator = serializer.save()
        return Response(CoordinatorSerializer(coordinator).data, status=status.HTTP_201_CREATED)


class AdminCoordinatorDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CoordinatorSerializer
    permission_classes = [IsAdmin]
    queryset = Coordinator.objects.select_related("user").all()

    def perform_update(self, serializer):
        coordinator = serializer.instance
        user_data = self.request.data
        user = coordinator.user
        if "name" in user_data:
            user.full_name = user_data["name"]
        if "phone" in user_data:
            user.phone = user_data["phone"]
        user.save()
        serializer.save()

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        user.delete()


class ToggleCoordinatorActiveView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            coordinator = Coordinator.objects.get(pk=pk)
        except Coordinator.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        coordinator.is_active = not coordinator.is_active
        coordinator.save(update_fields=["is_active"])
        coordinator.user.is_active_account = coordinator.is_active
        coordinator.user.save(update_fields=["is_active_account"])
        return Response(CoordinatorSerializer(coordinator).data)


# ----------------------------------------------------------- coordinator self-service

class MyCoordinatorEventsView(generics.ListAPIView):
    """Coordinator: events assigned to me."""

    serializer_class = EventListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        coordinator = getattr(self.request.user, "coordinator_profile", None)
        if not coordinator:
            return Event.objects.none()
        return coordinator.assigned_events.all()


class MyCoordinatorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        coordinator = getattr(request.user, "coordinator_profile", None)
        if not coordinator:
            return Response({"detail": "Not a coordinator."}, status=403)
        events = coordinator.assigned_events.all()
        total_registrations = FormSubmission.objects.filter(event__in=events).count()
        recent = FormSubmission.objects.filter(event__in=events).order_by("-submitted_at")[:10]
        return Response({
            "assigned_events": EventListSerializer(events, many=True).data,
            "total_registrations": total_registrations,
            "recent_registrations": [
                {
                    "id": s.id,
                    "registration_id": s.registration_id,
                    "event": s.event.name,
                    "submitted_at": s.submitted_at,
                    "status": s.status,
                }
                for s in recent
            ],
            "event_statistics": [
                {"event": e.name, "registrations": e.registration_count, "capacity": e.max_participants}
                for e in events
            ],
        })
