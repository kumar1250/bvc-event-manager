from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdmin, IsAdminOrCoordinator
from notifications.email_utils import send_event_cancellation_email, send_event_update_email
from notifications.models import Notification

from .models import Event, EventFlowStep
from .serializers import (
    EventDetailSerializer,
    EventFlowStepSerializer,
    EventListSerializer,
    EventWriteSerializer,
)
from .utils import normalize_image_url


class EventListView(generics.ListAPIView):
    """Public: browse + search + filter events."""

    serializer_class = EventListSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "category": ["exact"],
        "status": ["exact"],
        "date": ["exact", "gte", "lte"],
    }
    search_fields = ["name", "venue", "category", "description"]
    ordering_fields = ["date", "start_time", "name", "created_at"]
    ordering = ["date"]

    def get_queryset(self):
        qs = Event.objects.exclude(status=Event.Status.DRAFT)
        upcoming = self.request.query_params.get("upcoming")
        if upcoming == "true":
            qs = qs.filter(date__gte=timezone.now().date())
        return qs


class EventDetailView(generics.RetrieveAPIView):
    serializer_class = EventDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "pk"
    queryset = Event.objects.all()

    def get_object(self):
        lookup = self.kwargs["pk"]
        qs = self.get_queryset()
        if str(lookup).isdigit():
            return generics.get_object_or_404(qs, pk=lookup)
        return generics.get_object_or_404(qs, slug=lookup)


class AdminEventListCreateView(generics.ListCreateAPIView):
    """Admin: full CRUD list/create. Coordinators get read-only list of their events elsewhere."""

    permission_classes = [IsAdmin]
    queryset = Event.objects.all().order_by("-created_at")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "status"]
    search_fields = ["name", "venue"]

    def get_serializer_class(self):
        return EventListSerializer if self.request.method == "GET" else EventWriteSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        if data.get("banner_image_url"):
            data["banner_image_url"] = normalize_image_url(data["banner_image_url"])
        serializer.save(created_by=self.request.user)


class AdminEventDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    queryset = Event.objects.all()

    def get_serializer_class(self):
        return EventDetailSerializer if self.request.method == "GET" else EventWriteSerializer

    def perform_update(self, serializer):
        data = serializer.validated_data
        if data.get("banner_image_url"):
            data["banner_image_url"] = normalize_image_url(data["banner_image_url"])
        event = serializer.save()

        # Notify registered users of material changes.
        recipients = [
            s.user for s in event.submissions.select_related("user").filter(user__isnull=False)
        ]
        if recipients:
            message = "Details for this event have been updated. Please review the latest information."
            send_event_update_email(event, recipients, message)
            Notification.objects.bulk_create([
                Notification(
                    user=u, type=Notification.Type.EVENT_UPDATED,
                    title=f"{event.name} was updated", message=message,
                )
                for u in recipients
            ])

    def perform_destroy(self, instance):
        recipients = [
            s.user for s in instance.submissions.select_related("user").filter(user__isnull=False)
        ]
        if instance.status == Event.Status.CANCELLED and recipients:
            send_event_cancellation_email(instance, recipients)
        instance.delete()


class CancelEventView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            return Response({"detail": "Event not found."}, status=404)
        event.status = Event.Status.CANCELLED
        event.save(update_fields=["status"])
        recipients = [
            s.user for s in event.submissions.select_related("user").filter(user__isnull=False)
        ]
        if recipients:
            send_event_cancellation_email(event, recipients)
            Notification.objects.bulk_create([
                Notification(
                    user=u, type=Notification.Type.EVENT_CANCELLED,
                    title=f"{event.name} was cancelled",
                    message=f"{event.name} scheduled on {event.date} has been cancelled.",
                )
                for u in recipients
            ])
        return Response({"detail": "Event cancelled and registrants notified."})


# ---------------------------------------------------------------- flow steps

class EventFlowListCreateView(generics.ListCreateAPIView):
    serializer_class = EventFlowStepSerializer
    permission_classes = [IsAdminOrCoordinator]

    def get_queryset(self):
        return EventFlowStep.objects.filter(event_id=self.kwargs["event_id"])

    def perform_create(self, serializer):
        serializer.save(event_id=self.kwargs["event_id"])


class EventFlowDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EventFlowStepSerializer
    permission_classes = [IsAdminOrCoordinator]

    def get_queryset(self):
        return EventFlowStep.objects.filter(event_id=self.kwargs["event_id"])


class EventFlowReorderView(APIView):
    """Body: {"order": [step_id, step_id, ...]} in the new desired order."""

    permission_classes = [IsAdminOrCoordinator]

    def post(self, request, event_id):
        order = request.data.get("order", [])
        steps = {s.id: s for s in EventFlowStep.objects.filter(event_id=event_id, id__in=order)}
        updated = []
        for index, step_id in enumerate(order):
            step = steps.get(step_id)
            if step:
                step.order = index
                updated.append(step)
        EventFlowStep.objects.bulk_update(updated, ["order"])
        return Response(EventFlowStepSerializer(
            EventFlowStep.objects.filter(event_id=event_id).order_by("order"), many=True
        ).data)
