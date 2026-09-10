from django.utils import timezone
from rest_framework import generics, status, filters
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

from core.permissions import IsAdmin
from notifications.email_utils import send_password_reset_email, send_welcome_email
from .models import PasswordResetToken, User
from .serializers import (
    AdminUserUpdateSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_welcome_email(user)
        tokens = _tokens_for_user(user)
        return Response(
            {"user": UserSerializer(user).data, **tokens},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = _tokens_for_user(user)
        return Response({"user": UserSerializer(user).data, **tokens})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response({"old_password": "Incorrect password."}, status=400)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"detail": "Password changed successfully."})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower().strip()
        # Always respond the same way, whether or not the email exists,
        # so this endpoint can't be used to enumerate registered accounts.
        try:
            user = User.objects.get(email__iexact=email)
            reset_token = PasswordResetToken.objects.create(user=user)
            send_password_reset_email(user, reset_token.token)
        except User.DoesNotExist:
            pass
        return Response(
            {"detail": "If an account exists with that email, a reset link has been sent."}
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        try:
            reset_token = PasswordResetToken.objects.select_related("user").get(token=token)
        except PasswordResetToken.DoesNotExist:
            return Response({"detail": "Invalid or expired reset link."}, status=400)
        if not reset_token.is_valid:
            return Response({"detail": "This reset link has expired."}, status=400)
        user = reset_token.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        reset_token.used = True
        reset_token.save(update_fields=["used"])
        return Response({"detail": "Password has been updated. You can now log in."})


class AdminUserListView(generics.ListAPIView):
    """Admin: list/search/filter all users."""

    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all().order_by("-date_joined")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["role", "is_active_account"]
    search_fields = ["full_name", "email", "phone"]


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: view/edit/deactivate/delete/change-role of a user."""

    serializer_class = AdminUserUpdateSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method == "GET":
            return UserSerializer
        return AdminUserUpdateSerializer


class AdminResetUserPasswordView(APIView):
    """Admin: force-send a password reset link to a user."""

    permission_classes = [IsAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)
        reset_token = PasswordResetToken.objects.create(user=user)
        send_password_reset_email(user, reset_token.token)
        return Response({"detail": "Password reset link sent."})
