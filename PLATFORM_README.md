# Dynamic Event Management Platform — Backend

This adds a full multi-event, dynamic-form registration platform on top of the
existing project. **The original `teams` app (single-hackathon, Google Sheets
backed) is untouched and still works** — it's mounted at `/api/...` exactly as
before. The new platform is namespaced at `/api/v2/...` to avoid colliding
with routes `teams` already owns (e.g. `teams` already had `forms/<id>/submit/`).

No frontend was built — backend only, per request.

---

## 1. What was implemented

- **Auth** (`accounts`): custom `User` model (email login, roles: admin /
  coordinator / user), JWT auth (access + refresh), register, login,
  forgot/reset password (expiring tokens), change password, admin user
  management (search/filter/edit role/deactivate/force-reset-password).
- **Events** (`events`): full CRUD, slugs, categories, capacity/seat tracking,
  registration windows, statuses (draft → upcoming → registration open/closed
  → ongoing → completed/cancelled), editable/reorderable **event flow
  timeline**, Google Drive share-link → direct image URL conversion (falls
  back gracefully for normal image URLs), cancel-event flow that emails every
  registrant.
- **Coordinators** (`coordinators`): admin creates a coordinator (creates the
  User + profile + emails nothing sensitive — password is set by admin),
  assign events, activate/deactivate, coordinator self-service dashboard
  scoped to *only* their assigned events (enforced server-side).
- **Dynamic form engine** (`forms`) — the core feature:
  - `RegistrationForm → FormField → FieldOption` and
    `FormSubmission → FormAnswer` — fully relational, no hardcoded columns.
  - 19 field types (short/long text, email, phone, number, radio, checkbox,
    dropdown, multiselect, date/time/datetime, URL, address, image URL, file
    upload, section/heading/description, terms & conditions).
  - Per-field settings: placeholder, description, required, default value,
    min/max length, min/max value, regex validation, order.
  - **Conditional logic**: any field can depend on another field's value
    (e.g. "Team Name" only required if "Participating as team?" = "Yes").
    Hidden fields are skipped entirely, not just hidden client-side.
  - Builder save is a full-replace PUT (`/admin/<id>/builder/`) — the
    standard pattern for a drag-and-drop builder; simplest and most reliable.
  - Draft / Active / Inactive / Closed status; only Active forms (and only
    within the event's registration window / while seats remain) accept
    submissions.
  - Submission validates required fields, type-specific rules, and option
    membership server-side; generates a unique `EVT-YYYY-NNNNN` registration
    ID; capacity-checked; sends a confirmation email; creates an in-app
    notification for logged-in users.
- **Notifications** (`notifications`): in-app `Notification` model +
  **Brevo** transactional email (welcome, password reset, registration
  confirmation, event update, event cancellation) — see section 3. Every send
  is logged to `EmailLog` and failures never raise (a broken email provider
  won't break registration).
- **Registrations / exports**: cross-event admin registration list
  (coordinators see only their assigned events), CSV / Excel / PDF export
  with **dynamic columns** derived from whichever fields each form actually
  has, filterable by status, exportable per-event or per-form or globally.
- **Dashboard** (`dashboardapi`): admin stats (cards + charts: registrations
  over time / by event / by category, department distribution, popular
  events) and a per-user "my dashboard" endpoint.
- **Security**: JWT auth, password hashing (Django default, PBKDF2), role
  checks enforced server-side via DRF permission classes (never trust the
  frontend), input validation via serializers, `django-filter` for safe
  querying, CORS via `django-cors-headers`, throttle scope on auth endpoints,
  password-reset tokens expire after 1 hour and are single-use, forgot
  password doesn't leak whether an email exists.

---

## 2. Files created / modified

New apps (all files new): `accounts/`, `events/`, `coordinators/`, `forms/`,
`notifications/`, `dashboardapi/`.

Also new: `core/permissions.py` (shared DRF permission classes).

Modified:
- `core/settings.py` — new apps registered, `AUTH_USER_MODEL`, DRF/JWT
  config, Brevo env vars, `URL_FORMAT_OVERRIDE: None` (see note below).
- `core/urls.py` — new routes mounted under `/api/v2/`, legacy `teams` left
  exactly as it was under `/api/`.
- `requirements.txt` — appended `django-filter`, `reportlab`, `requests`.
- `.env` — appended `SECRET_KEY`, `DEBUG`, `FRONTEND_URL`, `BREVO_*` (your
  original Google Sheets credentials are untouched).

Not modified: everything under `teams/`.

**Note on `URL_FORMAT_OVERRIDE`:** DRF reserves the query parameter
`?format=` to override the response renderer. It was disabled globally
because it silently 404s any endpoint that happens to use `format` as its
own query param name (this bit the export endpoints during testing — now
fixed by using `?type=csv|excel|pdf` instead). Disabling it does not affect
anything else in the API.

---

## 2a. Update — database via URL, multiple forms per event

Two follow-up changes on top of the original build:

- **`DATABASE_URL`**: `core/settings.py` now reads a `DATABASE_URL` env var
  (via `dj-database-url`) and uses it if set — e.g.
  `postgres://user:pass@host:5432/dbname` or `mysql://user:pass@host:3306/db`.
  Leave it blank/unset and it falls back to local sqlite automatically, so
  nothing changes for local dev. Install the matching DB driver yourself
  (commented-out lines for `psycopg[binary]` / `mysqlclient` are in
  `requirements.txt`) — it isn't installed by default since we don't know
  which database you'll use.
- **Multiple active forms per event**: `GET /events/<id_or_slug>/` now also
  returns `active_forms: [{id, title, description}, ...]` — every `active`
  form for that event, not just one. This supports events that run several
  registration forms at once (e.g. a fest with a "Drawing" activity and a
  separate "Quiz" activity, each with its own form). `active_form_id` is
  still returned for backward compatibility (points at the most recent one).

## 3. Environment variables required

Already appended to your `.env`:

```
SECRET_KEY=django-insecure-CHANGE-THIS-BEFORE-DEPLOYING   # replace before deploying
DEBUG=True
FRONTEND_URL=http://localhost:5173      # used to build links inside emails

BREVO_API_KEY=            # from https://app.brevo.com/settings/keys/api
BREVO_SENDER_EMAIL=       # must be a verified sender in your Brevo account
BREVO_SENDER_NAME=Event Platform

# Optional - overrides the default local sqlite database. Leave blank for local dev.
#   postgres://user:password@host:5432/dbname
#   mysql://user:password@host:3306/dbname
DATABASE_URL=
```

Until `BREVO_API_KEY` / `BREVO_SENDER_EMAIL` are filled in, emails are
skipped (logged as a warning + an `EmailLog` row with `success=False`) —
registration/signup itself still succeeds.

---

## 4. Database migrations

Already generated and included under each app's `migrations/` folder.

To apply on your machine:

```bash
pip install -r requirements.txt
python manage.py migrate
```

**Important:** this introduces a custom `AUTH_USER_MODEL`
(`accounts.User`), which Django cannot retrofit onto an existing database
that already has data in the built-in `auth_user` table. If you have a
database with real data already in it, either:
- start from a fresh database (recommended for dev), or
- ask for a data-migration script to move any existing users over (not
  included here since your current DB only had `teams`-app data, which
  doesn't touch `auth_user` beyond admin logins).

---

## 5. Commands to run the backend

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # or use the test admin below
python manage.py runserver
```

No frontend was built in this task.

---

## 6. Test credentials

A dev admin was created during testing:

```
email:    admin@eventplatform.com
password: Admin@12345
role:     admin
```

(This exists only in the sandbox DB used to test — run
`python manage.py createsuperuser` or the shell snippet below to create
your own on a fresh database.)

```python
python manage.py shell -c "
from accounts.models import User
u = User(email='admin@eventplatform.com', username='admin@eventplatform.com',
         full_name='Platform Admin', role='admin', is_staff=True, is_superuser=True)
u.set_password('Admin@12345')
u.save()
"
```

---

## 7. API overview (all under `/api/v2/`)

```
auth/register/                          POST
auth/login/                             POST
auth/token/refresh/                     POST
auth/me/                                GET, PATCH
auth/change-password/                   POST
auth/forgot-password/                   POST
auth/reset-password/                    POST
auth/admin/users/                       GET (search/filter)
auth/admin/users/<id>/                  GET, PATCH, DELETE
auth/admin/users/<id>/reset-password/   POST

events/                                 GET (public, search/filter)
events/<id_or_slug>/                    GET (public)
events/admin/list/                      GET, POST
events/admin/<id>/                      GET, PATCH, DELETE
events/admin/<id>/cancel/               POST
events/<id>/flow/                       GET, POST
events/<id>/flow/<id>/                  GET, PATCH, DELETE
events/<id>/flow/reorder/               POST  {"order": [id, id, ...]}

coordinators/                           GET (public)
coordinators/admin/list/                GET, POST
coordinators/admin/<id>/                GET, PATCH, DELETE
coordinators/admin/<id>/toggle-active/  POST
coordinators/me/events/                 GET
coordinators/me/dashboard/              GET

forms/<id>/                             GET (public form schema, if active)
forms/<id>/submit/                      POST (public submission)
forms/admin/list/                       GET, POST
forms/admin/<id>/                       GET, PATCH, DELETE
forms/admin/<id>/builder/               GET, PUT (full field-list replace)
forms/admin/<id>/status/                POST {"status": "draft|active|inactive|closed"}
forms/admin/<id>/responses/             GET
forms/admin/<id>/responses/export/      GET ?type=csv|excel|pdf
forms/submissions/<id>/                 GET, DELETE
forms/submissions/<id>/status/          POST {"status": "approved|rejected"}

registrations/                          GET (cross-event, admin/coordinator)
registrations/export/                   GET ?type=csv|excel|pdf&status=...
registrations/export/event/<id>/        GET ?type=csv|excel|pdf
registrations/mine/                     GET (user's own registrations)
registrations/mine/<id>/                GET

notifications/                          GET
notifications/<id>/read/                POST
notifications/read-all/                 POST

dashboard/stats/                        GET (admin: cards + charts)
dashboard/me/                           GET (user: registered/upcoming events)
```

---

## 8. Tested end-to-end (on a fresh DB, via a live dev server)

- Admin login → create event (with Google Drive banner URL, auto-converted)
  → add event-flow step → create form → save builder with a conditional
  field ("Team Name" shown only if "Participating as team?" = "Yes") →
  activate form.
- Public: fetch form schema, submit a valid registration → 201 +
  unique registration ID; submit an invalid one (missing required fields,
  bad email) → 400 with per-field errors; conditional field correctly
  **not** required when its condition isn't met.
- Admin: registrations list, CSV/Excel/PDF export (dynamic columns), full
  dashboard stats.
- Coordinator creation, login, and coordinator-scoped dashboard.
- Regular user self-registration.
- Public event detail correctly reflects seats remaining and the active
  form id.
- Confirmed the legacy `teams` endpoints still resolve to their original
  views (no route collisions) — the only failure there is a pre-existing
  Google Sheets network call blocked by this sandbox's own egress allowlist,
  unrelated to anything changed here.

---

## 9. Remaining / known limitations

- **File Upload** field type stores whatever value is submitted (e.g. a URL
  to an already-uploaded file) — actual file storage/upload handling
  (S3, Django `FileField`, etc.) wasn't wired up, since no frontend or
  storage backend was specified. Swap in real file handling before using
  this field type in production.
- **Rate limiting** is only applied to the four core auth endpoints
  (register/login/forgot/reset) via `ScopedRateThrottle`. Extend
  `throttle_scope` to other sensitive endpoints (e.g. submission) if needed.
- **Registration-closing-soon** notifications are modeled
  (`Notification.Type.REGISTRATION_CLOSING`) but nothing currently schedules
  them — would need a periodic task (Celery beat / cron +
  `manage.py` command) to scan events nearing `registration_end`.
- No automated test suite (pytest/unittest) was written — verification was
  done via a live end-to-end script exercising every major flow. Recommend
  adding `pytest-django` tests before production use.
- `SECRET_KEY` in `.env` is a placeholder — replace it before deploying.
