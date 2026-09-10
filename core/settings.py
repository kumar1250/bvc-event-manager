"""
Django settings for the BVC Hackathon Registration project.
"""

from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: change this before deploying to production!
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-CHANGE-THIS-BEFORE-DEPLOYING-xk29d8f7h2j",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt",
    "django_filters",
    "teams",
    # Dynamic Event Management Platform
    "accounts",
    "events",
    "coordinators",
    "forms",
    "notifications",
    "dashboardapi",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# CORS - allow the React dev server / deployed frontend to call this API.
# For production, replace with your actual frontend domain(s).
CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

import dj_database_url

# DATABASE_URL, e.g.:
#   postgres://user:password@host:5432/dbname
#   mysql://user:password@host:3306/dbname
#   sqlite:///db.sqlite3
# Falls back to local sqlite if DATABASE_URL isn't set (or is set but blank),
# so local dev needs no setup.
_database_url = os.environ.get("DATABASE_URL", "").strip()
DATABASES = {
    "default": dj_database_url.parse(_database_url, conn_max_age=600, conn_health_checks=True)
    if _database_url
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "auth": "20/minute",
    },
    # Disable the '?format=' query-param override entirely - it silently
    # breaks any endpoint whose own query params happen to use that name
    # (e.g. our CSV/Excel/PDF export `type` param used to be named `format`).
    "URL_FORMAT_OVERRIDE": None,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

# ---- Brevo (transactional email) ----
# https://app.brevo.com/settings/keys/api
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "Event Platform")

# Base URL of the deployed frontend, used to build links inside emails
# (e.g. the password-reset link).
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# ---- Data storage ----
# Team registrations, problem statements, and app settings are now stored
# in a Google Sheet (see teams/gsheet_utils.py) instead of local .xlsx
# files, so data survives Render restarts/redeploys on the free tier.
# Configure via the GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON env
# vars — see GOOGLE_SHEETS_SETUP.md.
DATA_DIR = BASE_DIR / "data"

def _parse_admin_users(raw):
    admins = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        username, password = pair.split(":", 1)
        admins[username.strip()] = password.strip()
    return admins

ADMIN_USERS = _parse_admin_users(os.environ.get("ADMIN_USERS", ""))