from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from coordinators.models import Coordinator
from events.models import Event
from forms.models import FormSubmission, RegistrationForm
from forms.serializers import FormSubmissionListSerializer

from core.permissions import IsAdmin, IsAdminOrCoordinator


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        registrations_over_time = list(
            FormSubmission.objects.annotate(day=TruncDate("submitted_at"))
            .values("day").annotate(count=Count("id")).order_by("day")
        )
        registrations_by_event = list(
            FormSubmission.objects.values("event__name")
            .annotate(count=Count("id")).order_by("-count")[:10]
        )
        registrations_by_category = list(
            FormSubmission.objects.values("event__category")
            .annotate(count=Count("id")).order_by("-count")
        )
        department_distribution = list(
            FormSubmission.objects.filter(answers__field__label__iexact="Department")
            .values("answers__value").annotate(count=Count("id")).order_by("-count")[:15]
        )
        popular_events = list(
            Event.objects.annotate(reg_count=Count("submissions"))
            .order_by("-reg_count")[:5].values("name", "reg_count")
        )

        return Response({
            "cards": {
                "total_events": Event.objects.count(),
                "active_events": Event.objects.filter(
                    status__in=[Event.Status.UPCOMING, Event.Status.REGISTRATION_OPEN, Event.Status.ONGOING]
                ).count(),
                "total_users": User.objects.filter(role=User.Role.USER).count(),
                "total_registrations": FormSubmission.objects.count(),
                "total_coordinators": Coordinator.objects.count(),
                "active_forms": RegistrationForm.objects.filter(status=RegistrationForm.Status.ACTIVE).count(),
            },
            "charts": {
                "registrations_over_time": [
                    {"date": r["day"], "count": r["count"]} for r in registrations_over_time
                ],
                "registrations_by_event": [
                    {"event": r["event__name"], "count": r["count"]} for r in registrations_by_event
                ],
                "registrations_by_category": [
                    {"category": r["event__category"], "count": r["count"]} for r in registrations_by_category
                ],
                "department_distribution": [
                    {"department": r["answers__value"], "count": r["count"]} for r in department_distribution
                ],
                "popular_events": popular_events,
            },
        })


class MyDashboardView(APIView):
    """Regular user: /dashboard - registered events, upcoming events, registration history."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        submissions = FormSubmission.objects.filter(user=request.user).select_related("event")
        registered_event_ids = submissions.values_list("event_id", flat=True)
        upcoming = Event.objects.filter(
            id__in=registered_event_ids, date__gte=timezone.now().date()
        ).exclude(status=Event.Status.CANCELLED)

        return Response({
            "registered_events_count": registered_event_ids.distinct().count(),
            "upcoming_events": [
                {"id": e.id, "name": e.name, "date": e.date, "venue": e.venue, "status": e.status}
                for e in upcoming
            ],
            "registration_history": FormSubmissionListSerializer(
                submissions.order_by("-submitted_at"), many=True
            ).data,
        })
