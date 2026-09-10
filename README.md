# Hackathon Registration — Backend

Django + Django REST Framework. Registrations are stored in an Excel
workbook (`data/teams.xlsx`), not a SQL table — see `teams/excel_utils.py`.
The default SQLite database (`db.sqlite3`) is only used for Django's
built-in auth (admin login).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # creates your admin dashboard login

python manage.py runserver
```

The API runs on http://127.0.0.1:8000/api/.

## How registrations are stored

`data/teams.xlsx` is created automatically on first use, with headers.
Each row is one team. Opening/editing it manually in Excel is fine as
long as the server isn't writing to it at that exact moment — a write
while the file is open elsewhere returns a clear "file is open elsewhere"
error to the person registering rather than corrupting the sheet.

## API summary

Public:
- `POST /api/register/` — submit a team registration
- `GET /api/check-name/<team_name>/` — check if a team name is taken

Admin (all require `Authorization: Bearer <access token>` from login):
- `POST /api/admin/login/` — get access + refresh tokens
- `POST /api/admin/token/refresh/`
- `GET /api/admin/teams/?search=&track=` — list/search/filter registrations
- `DELETE /api/admin/teams/<team_id>/` — remove a registration
- `GET /api/admin/dashboard/` — summary stats
- `GET /api/admin/download/` — download `teams.xlsx`

## Creating more admin logins

Admin dashboard access = any Django user with `is_staff=True`. Create more
via `python manage.py createsuperuser`, or Django's `/admin/` panel.

## Before deploying for real

- Set `DEBUG=False` and a real `SECRET_KEY` via environment variables
  (both already read from `os.environ` in `core/settings.py`)
- Narrow `ALLOWED_HOSTS` and `CORS_ALLOW_ALL_ORIGINS` to your actual domain
- Serve with gunicorn (included in requirements.txt) behind Nginx, not
  `manage.py runserver`
- Back up `data/teams.xlsx` regularly — it's the only copy of your
  registration data
"# hackthon-hub-backend" 
