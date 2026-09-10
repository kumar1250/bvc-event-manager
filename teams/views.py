from django.contrib.auth import authenticate
from django.core import signing
from django.http import FileResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from . import settings_utils as app_settings
from rest_framework_simplejwt.tokens import RefreshToken
from . import problems_excel_utils as ps
from . import forms_utils
from .serializers import (
    ProblemStatementSerializer,
    ProblemStatementUpdateSerializer,
    RegistrationSerializer,
    TeamLoginSerializer,
    ChooseProblemSerializer,
    TeamIdeaSerializer,
    FormSerializer,
    FormUpdateSerializer,
)
from django.conf import settings
from django.contrib.auth import get_user_model, authenticate

from . import excel_utils
from rest_framework.decorators import api_view, permission_classes, authentication_classes



# ---------- Team-leader auth helpers ----------
# Team leaders don't get a Django User account — they log in with just
# their roll number, and we hand back a signed token (no extra DB/table
# needed) that encodes which team they are. It is verified on every
# team/* request below.

TEAM_TOKEN_SALT = "team-leader-auth"
TEAM_TOKEN_MAX_AGE = 60 * 60 * 12  # 12 hours


def _make_team_token(team_id):
    return signing.dumps({"team_id": team_id}, salt=TEAM_TOKEN_SALT)


def _team_id_from_request(request):
    """Returns the team_id encoded in the request's bearer token, or
    None if it's missing/invalid/expired."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    try:
        data = signing.loads(token, salt=TEAM_TOKEN_SALT, max_age=TEAM_TOKEN_MAX_AGE)
        return data.get("team_id")
    except signing.BadSignature:
        return None


# ---------- Public ----------

@api_view(["POST"])
@permission_classes([AllowAny])
def register_team(request):
    serializer = RegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    try:
        team_id = excel_utils.save_team(serializer.validated_data)
    except ValueError as e:
        return Response({"error": str(e)}, status=400)
    except PermissionError as e:
        return Response({"error": str(e)}, status=503)

    return Response({"message": "Registration successful", "team_id": team_id}, status=201)


@api_view(["GET"])
@permission_classes([AllowAny])
def check_team_name(request, team_name):
    exists = excel_utils.find_team_by_name(team_name) is not None
    return Response({"exists": exists})


# ---------- Team leader auth + problem-statement selection ----------

@api_view(["POST"])
@permission_classes([AllowAny])
def team_login(request):
    serializer = TeamLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    team = excel_utils.find_team_by_roll_no(serializer.validated_data["roll_no"])
    if team is None:
        return Response(
            {"error": "No team found for that roll number. Check with the organizers if you've already registered."},
            status=404,
        )

    token = _make_team_token(team["team_id"])
    return Response({
        "token": token,
        "team_id": team["team_id"],
        "team_name": team["team_name"],
        "leader_name": team["leader_name"],
    })


@api_view(["GET", "PATCH"])
@authentication_classes([])
@permission_classes([AllowAny])
def team_me(request):
    team_id = _team_id_from_request(request)
    if team_id is None:
        return Response({"error": "Not logged in, or session expired. Please log in again."}, status=401)

    if request.method == "PATCH":
        team = excel_utils.update_team(team_id, request.data)
        if team is None:
            return Response({"error": "Team not found."}, status=404)
        return Response(team)

    team = excel_utils.get_team_by_id(team_id)
    if team is None:
        return Response({"error": "Team not found."}, status=404)
    return Response(team)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def team_choose_problem(request):
    """Set or change the single problem statement this team has chosen."""
    team_id = _team_id_from_request(request)
    if team_id is None:
        return Response({"error": "Not logged in, or session expired. Please log in again."}, status=401)

    serializer = ChooseProblemSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    problem = ps.get_problem(serializer.validated_data["problem_id"])
    if problem is None:
        return Response({"error": "That problem statement doesn't exist."}, status=404)

    updated = excel_utils.set_team_problem(team_id, problem["id"], problem["title"])
    if updated is None:
        return Response({"error": "Team not found."}, status=404)
    return Response(updated)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def team_save_idea(request):
    team_id = _team_id_from_request(request)
    if team_id is None:
        return Response({"error": "Not logged in, or session expired. Please log in again."}, status=401)

    serializer = TeamIdeaSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)

    updated = excel_utils.set_team_idea(team_id, serializer.validated_data["idea"])
    if updated is None:
        return Response({"error": "Team not found."}, status=404)
    return Response(updated)


# ---------- Admin auth ----------

@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "").strip()

    # Hardcoded admin users
    ADMIN_USERS = {
        "kumar": "kumar@8121",
        "harshal": "harshal1223",
        "Anilkumar": "Anilkumar@123",
        "mounika": "mounika@1227",
        "saiprasad": "saiprasad@501",
        "sai": "sai@1239",
        "Bhavani": "Bhavani@123",
    }

    User = get_user_model()

    # First try normal Django authentication (superuser)
    user = authenticate(username=username, password=password)

    # If not a Django user, check hardcoded admins
    if user is None:
        if username not in ADMIN_USERS or ADMIN_USERS[username] != password:
            return Response({"error": "Invalid credentials"}, status=401)

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "is_staff": True,
                "is_superuser": False,
                "is_active": True,
            },
        )

        if created:
            # Set any password so the model is valid
            user.set_password(password)
            user.save()
        else:
            user.is_staff = True
            user.is_active = True
            user.save(update_fields=["is_staff", "is_active"])

    if not user.is_staff:
        return Response({"error": "You are not an admin"}, status=403)

    refresh = RefreshToken.for_user(user)

    return Response({
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "username": user.username,
    })

# ---------- Admin (JWT required) ----------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_teams(request):
    search = request.query_params.get("search")
    track = request.query_params.get("track")
    teams = excel_utils.get_all_teams(search=search, track=track)
    return Response({"count": len(teams), "teams": teams})


@api_view(["DELETE", "PATCH"])
@permission_classes([IsAuthenticated])
def delete_team(request, team_id):
    if request.method == "PATCH":
        team = excel_utils.update_team(team_id, request.data)
        if not team:
            return Response({"error": "Team not found"}, status=404)
        return Response(team)

    deleted = excel_utils.delete_team(team_id)
    if not deleted:
        return Response({"error": "Team not found"}, status=404)
    return Response({"message": "Deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard(request):
    return Response(excel_utils.get_dashboard_stats())


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_teams(request):
    return FileResponse(
        excel_utils.export_xlsx_bytes(),
        as_attachment=True,
        filename="teams.xlsx",
    )




# ---------- Public: read-only, so participants can see the problem list ----------

# @api_view(["GET"])
# @permission_classes([AllowAny])
# def list_problems_public(request):
#     problems = ps.get_all_problems(
#         search=request.query_params.get("search"),
#         track=request.query_params.get("track"),
#         difficulty=request.query_params.get("difficulty"),
#     )
#     return Response({"count": len(problems), "problems": problems})


# ---------- Admin (JWT required): CRUD ----------

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_problems(request):
    if request.method == "GET":
        problems = ps.get_all_problems(
            search=request.query_params.get("search"),
            track=request.query_params.get("track"),
            difficulty=request.query_params.get("difficulty"),
        )
        return Response({"count": len(problems), "problems": problems})

    # POST -> create
    serializer = ProblemStatementSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    try:
        problem_id = ps.create_problem(serializer.validated_data)
    except PermissionError as e:
        return Response({"error": str(e)}, status=503)
    return Response(ps.get_problem(problem_id), status=201)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_problem_detail(request, problem_id):
    if request.method == "GET":
        problem = ps.get_problem(problem_id)
        if not problem:
            return Response({"error": "Problem statement not found"}, status=404)
        return Response(problem)

    if request.method == "DELETE":
        deleted = ps.delete_problem(problem_id)
        if not deleted:
            return Response({"error": "Problem statement not found"}, status=404)
        return Response({"message": "Deleted"})

    # PUT / PATCH -> update
    serializer = ProblemStatementUpdateSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    try:
        updated = ps.update_problem(problem_id, serializer.validated_data)
    except PermissionError as e:
        return Response({"error": str(e)}, status=503)
    if not updated:
        return Response({"error": "Problem statement not found"}, status=404)
    return Response(updated)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_problems(request):
    return FileResponse(
        ps.export_xlsx_bytes(),
        as_attachment=True,
        filename="problem_statements.xlsx",
    )
    
@api_view(["GET"])
@permission_classes([AllowAny])
def list_problems_public(request):
    # Admin has to explicitly publish the problem statements first —
    # until then, participants see an empty list.
    if not app_settings.get_problems_visible():
        return Response({"count": 0, "problems": [], "visible": False})

    problems = ps.get_all_problems(
        search=request.query_params.get("search"),
        track=request.query_params.get("track"),
        difficulty=request.query_params.get("difficulty"),
    )
    return Response({"count": len(problems), "problems": problems, "visible": True})

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def admin_problems_visibility(request):
    if request.method == "GET":
        return Response({"visible": app_settings.get_problems_visible()})

    value = request.data.get("visible")
    if not isinstance(value, bool):
        return Response({"error": "'visible' must be true or false."}, status=400)
    visible = app_settings.set_problems_visible(value)
    return Response({"visible": visible})


# ---------- Site content: everything shown on the public Home page ----------
# Public — anyone can read it (that's the whole point, the site renders it).

@api_view(["GET"])
@permission_classes([AllowAny])
def site_content_public(request):
    return Response(app_settings.get_site_content())


# Admin — read/write the same object. PUT replaces the whole thing (any
# top-level key you omit keeps its previous value, so partial saves are
# safe too).

@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def admin_site_content(request):
    if request.method == "GET":
        return Response(app_settings.get_site_content())

    if not isinstance(request.data, dict):
        return Response({"error": "Expected a JSON object."}, status=400)

    updated = app_settings.set_site_content(request.data)
    return Response(updated)


# ---------- Dynamic Forms (Google-Forms-style form builder) ----------
# Admin builds a form out of arbitrary fields (text, choices, etc.), each
# of which can optionally be marked "unique" — meaning no two responses
# may submit the same value for it (handy for things like "roll number"
# or "email" fields where duplicates shouldn't be allowed).

# --- Admin: manage forms ---

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def admin_forms(request):
    if request.method == "GET":
        forms = forms_utils.get_all_forms(search=request.query_params.get("search"))
        return Response({"count": len(forms), "forms": forms})

    serializer = FormSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    try:
        form_id = forms_utils.create_form(serializer.validated_data)
    except PermissionError as e:
        return Response({"error": str(e)}, status=503)
    return Response(forms_utils.get_form(form_id), status=201)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def admin_form_detail(request, form_id):
    if request.method == "GET":
        form = forms_utils.get_form(form_id)
        if not form:
            return Response({"error": "Form not found"}, status=404)
        return Response(form)

    if request.method == "DELETE":
        deleted = forms_utils.delete_form(form_id)
        if not deleted:
            return Response({"error": "Form not found"}, status=404)
        return Response({"message": "Deleted"})

    serializer = FormUpdateSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    try:
        updated = forms_utils.update_form(form_id, serializer.validated_data)
    except PermissionError as e:
        return Response({"error": str(e)}, status=503)
    if not updated:
        return Response({"error": "Form not found"}, status=404)
    return Response(updated)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_form_responses(request, form_id):
    form = forms_utils.get_form(form_id)
    if not form:
        return Response({"error": "Form not found"}, status=404)
    responses = forms_utils.get_responses(form_id)
    return Response({"count": len(responses), "form": form, "responses": responses})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def admin_delete_response(request, form_id, response_id):
    deleted = forms_utils.delete_response(form_id, response_id)
    if not deleted:
        return Response({"error": "Response not found"}, status=404)
    return Response({"message": "Deleted"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_download_form_responses(request, form_id):
    form = forms_utils.get_form(form_id)
    if not form:
        return Response({"error": "Form not found"}, status=404)
    return FileResponse(
        forms_utils.export_responses_xlsx_bytes(form),
        as_attachment=True,
        filename=f"{form['title'] or 'form'}_responses.xlsx",
    )


# --- Public: fill out a form, Google-Forms style ---

@api_view(["GET"])
@permission_classes([AllowAny])
def public_form_detail(request, form_id):
    """Returns the form's field schema so the frontend can render it —
    only while the admin has it marked active/accepting responses."""
    form = forms_utils.get_form_public(form_id)
    if not form:
        return Response({"error": "This form isn't available right now."}, status=404)
    return Response(form)


@api_view(["POST"])
@permission_classes([AllowAny])
def public_form_submit(request, form_id):
    form = forms_utils.get_form_public(form_id)
    if not form:
        return Response({"error": "This form isn't available right now."}, status=404)

    if not isinstance(request.data, dict):
        return Response({"error": "Expected a JSON object of field answers."}, status=400)

    cleaned, errors = forms_utils.validate_response_data(form, request.data)
    if errors:
        return Response({"error": errors}, status=400)

    unique_errors = forms_utils.check_unique_fields(form, cleaned)
    if unique_errors:
        return Response({"error": unique_errors}, status=400)

    response_id = forms_utils.submit_response(form, cleaned)
    return Response({"message": "Response submitted", "response_id": response_id}, status=201)