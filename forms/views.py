from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdmin, IsAdminOrCoordinator
from events.models import Event
from notifications.email_utils import send_registration_confirmation_email
from notifications.models import Notification

from .exports import export_csv, export_excel, export_pdf
from .models import FormSubmission, RegistrationForm
from .serializers import (
    FormBuilderSaveSerializer,
    FormSubmissionDetailSerializer,
    FormSubmissionListSerializer,
    RegistrationFormListSerializer,
    RegistrationFormSerializer,
    RegistrationFormWriteSerializer,
)
from .services import create_submission


# --------------------------------------------------------------------- public

class PublicFormDetailView(generics.RetrieveAPIView):
    """Public: fetch the schema of an ACTIVE form to render for registration."""

    serializer_class = RegistrationFormSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return RegistrationForm.objects.prefetch_related("fields__options")

    def get_object(self):
        form = generics.get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        return form


class PublicFormSubmitView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        form = generics.get_object_or_404(RegistrationForm, pk=pk)
        event = form.event

        if not form.is_open:
            return Response({"detail": "Registration is currently closed."}, status=400)

        user = request.user if request.user and request.user.is_authenticated else None
        raw_answers = request.data.get("answers", {})

        try:
            submission = create_submission(form, event, user, raw_answers)
        except ValidationError as exc:
            return Response(exc.detail, status=400)

        send_registration_confirmation_email(submission)
        if user:
            Notification.objects.create(
                user=user, type=Notification.Type.REGISTRATION_SUCCESS,
                title=f"Registered for {event.name}",
                message=f"Your registration ID is {submission.registration_id}.",
            )

        return Response(FormSubmissionDetailSerializer(submission).data, status=201)


# ---------------------------------------------------------------------- admin

class AdminFormListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminOrCoordinator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["event", "status"]
    search_fields = ["title"]

    def get_queryset(self):
        return RegistrationForm.objects.select_related("event").all().order_by("-updated_at")

    def get_serializer_class(self):
        return RegistrationFormWriteSerializer if self.request.method == "POST" else RegistrationFormListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AdminFormDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrCoordinator]
    queryset = RegistrationForm.objects.prefetch_related("fields__options")

    def get_serializer_class(self):
        return RegistrationFormSerializer if self.request.method == "GET" else RegistrationFormWriteSerializer


class FormBuilderView(APIView):
    """GET: full schema for the builder UI. PUT: replace all fields (drag-and-drop save)."""

    permission_classes = [IsAdminOrCoordinator]

    def get(self, request, pk):
        form = generics.get_object_or_404(
            RegistrationForm.objects.prefetch_related("fields__options"), pk=pk
        )
        return Response(RegistrationFormSerializer(form).data)

    def put(self, request, pk):
        form = generics.get_object_or_404(RegistrationForm, pk=pk)
        serializer = FormBuilderSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(form)
        form.refresh_from_db()
        return Response(RegistrationFormSerializer(
            RegistrationForm.objects.prefetch_related("fields__options").get(pk=form.pk)
        ).data)


class FormStatusView(APIView):
    """POST {"status": "draft|active|inactive|closed"}"""

    permission_classes = [IsAdminOrCoordinator]

    def post(self, request, pk):
        form = generics.get_object_or_404(RegistrationForm, pk=pk)
        new_status = request.data.get("status")
        valid = dict(RegistrationForm.Status.choices)
        if new_status not in valid:
            return Response({"detail": f"status must be one of {list(valid)}"}, status=400)
        form.status = new_status
        form.save(update_fields=["status"])
        return Response(RegistrationFormListSerializer(form).data)


# ----------------------------------------------------------------- responses

class AdminFormResponsesView(generics.ListAPIView):
    serializer_class = FormSubmissionListSerializer
    permission_classes = [IsAdminOrCoordinator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["registration_id"]
    ordering_fields = ["submitted_at"]

    def get_queryset(self):
        return FormSubmission.objects.filter(form_id=self.kwargs["pk"]).select_related("event", "user")


class SubmissionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = FormSubmissionDetailSerializer
    permission_classes = [IsAdminOrCoordinator]
    queryset = FormSubmission.objects.select_related("event", "form", "user").prefetch_related("answers__field")


class SubmissionStatusView(APIView):
    """POST {"status": "approved" | "rejected"}"""

    permission_classes = [IsAdminOrCoordinator]

    def post(self, request, pk):
        submission = generics.get_object_or_404(FormSubmission, pk=pk)
        new_status = request.data.get("status")
        if new_status not in dict(FormSubmission.Status.choices):
            return Response({"detail": "Invalid status."}, status=400)
        submission.status = new_status
        submission.save(update_fields=["status"])
        return Response(FormSubmissionDetailSerializer(submission).data)


# ------------------------------------------------------------- registrations
# (cross-event registration management + exports)

class AdminRegistrationListView(generics.ListAPIView):
    serializer_class = FormSubmissionListSerializer
    permission_classes = [IsAdminOrCoordinator]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["event", "form", "status"]
    search_fields = ["registration_id"]
    ordering_fields = ["submitted_at"]

    def get_queryset(self):
        qs = FormSubmission.objects.select_related("event", "form", "user")
        user = self.request.user
        if user.role == "coordinator":
            coordinator = getattr(user, "coordinator_profile", None)
            allowed_events = coordinator.assigned_events.all() if coordinator else Event.objects.none()
            qs = qs.filter(event__in=allowed_events)
        return qs


EXPORTERS = {"csv": export_csv, "excel": export_excel, "pdf": export_pdf}


def _export_queryset(request, queryset, filename_base):
    fmt = request.query_params.get("type", "csv")
    exporter = EXPORTERS.get(fmt)
    if not exporter:
        return Response({"detail": "type must be csv, excel, or pdf."}, status=400)
    status_filter = request.query_params.get("status")
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    ext = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}[fmt]
    filename = f"{filename_base}.{ext}"
    if fmt == "pdf":
        return exporter(queryset, filename=filename, title=filename_base.replace("_", " ").title())
    return exporter(queryset, filename=filename)


class ExportAllRegistrationsView(APIView):
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request):
        qs = FormSubmission.objects.select_related("event", "form", "user")
        return _export_queryset(request, qs, "all_registrations")


class ExportEventRegistrationsView(APIView):
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request, event_id):
        qs = FormSubmission.objects.filter(event_id=event_id).select_related("event", "form", "user")
        return _export_queryset(request, qs, f"event_{event_id}_registrations")


class ExportFormResponsesView(APIView):
    permission_classes = [IsAdminOrCoordinator]

    def get(self, request, form_id):
        qs = FormSubmission.objects.filter(form_id=form_id).select_related("event", "form", "user")
        return _export_queryset(request, qs, f"form_{form_id}_responses")


# -------------------------------------------------------------- user-facing

class MyRegistrationsView(generics.ListAPIView):
    serializer_class = FormSubmissionListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FormSubmission.objects.filter(user=self.request.user).select_related("event", "form")


class MyRegistrationDetailView(generics.RetrieveAPIView):
    serializer_class = FormSubmissionDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FormSubmission.objects.filter(user=self.request.user).prefetch_related("answers__field")
