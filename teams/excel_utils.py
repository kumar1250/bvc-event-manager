"""
All reads/writes to the team-registration "database" live here.
Each row = one team registration, stored in the "Registrations" tab of
the Google Sheet (see gsheet_utils.py). Column order below must stay
in sync with HEADERS and TEAM_FIELDS.

This module keeps the exact same public function names/signatures it
had when it was backed by openpyxl + a local teams.xlsx file, so
views.py did not need to change.
"""

import io
import json
import threading
from datetime import datetime

from . import gsheet_utils

SHEET_NAME = "Registrations"

HEADERS = [
    "Team ID", "Team Name", "Track", "College / Organization",
    "Leader Name", "Leader Roll No", "Leader Email", "Leader Phone",
    "Members Count", "Members JSON", "Idea / Abstract", "Registered At",
    "Problem Statement ID", "Problem Statement Title",
]

TEAM_FIELDS = [
    "team_id", "team_name", "track", "college",
    "leader_name", "leader_roll_no", "leader_email", "leader_phone",
    "members_count", "members_json", "idea", "registered_at",
    "problem_id", "problem_title",
]

_lock = threading.Lock()


def _ensure_file():
    """Kept for backwards compatibility (views.py calls this before the
    xlsx-download endpoints). Makes sure the 'Registrations' worksheet
    and its header row exist, and returns the worksheet object."""
    return gsheet_utils.get_or_create_worksheet(SHEET_NAME, HEADERS)


def _all_rows():
    """Every data row (header excluded), as raw string lists padded/
    truncated to len(HEADERS)."""
    ws = _ensure_file()
    values = ws.get_all_values()[1:]
    rows = []
    width = len(HEADERS)
    for row in values:
        if not row or not (row[0] or "").strip():
            continue
        row = list(row) + [""] * (width - len(row))
        rows.append(row[:width])
    return rows


def _row_to_team(row):
    team = dict(zip(TEAM_FIELDS, row))
    team["team_id"] = int(team["team_id"]) if str(team["team_id"]).strip() else None
    try:
        team["members_count"] = int(team["members_count"] or 0)
    except (ValueError, TypeError):
        team["members_count"] = 0
    try:
        team["members"] = json.loads(team.get("members_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        team["members"] = []
    return team


def get_all_teams(search=None, track=None):
    teams = [_row_to_team(r) for r in _all_rows()]
    result = []
    for team in teams:
        if track and track.strip().lower() != (team["track"] or "").strip().lower():
            continue
        if search:
            s = search.strip().lower()
            member_names = " ".join(m.get("name", "") for m in team["members"])
            haystack = (
                f"{team['team_name']} {team['leader_name']} "
                f"{team['leader_roll_no']} {team['college']} {member_names}"
            ).lower()
            if s not in haystack:
                continue
        result.append(team)
    result.sort(key=lambda t: t["team_id"])
    result.reverse()
    return result


def find_team_by_name(team_name):
    target = team_name.strip().lower()
    for row in _all_rows():
        if row[1] and row[1].strip().lower() == target:
            return _row_to_team(row)
    return None


def find_team_by_roll_no(roll_no):
    """Look up a team by its leader's roll number (case-insensitive).
    Used for the team-leader login."""
    target = (roll_no or "").strip().lower()
    if not target:
        return None
    for row in _all_rows():
        if row[5] and row[5].strip().lower() == target:
            return _row_to_team(row)
    return None


def get_team_by_id(team_id):
    for row in _all_rows():
        if row[0] and int(row[0]) == int(team_id):
            return _row_to_team(row)
    return None


def _find_sheet_row(ws, team_id):
    """Returns (row_number, row_values) for the given team_id, or
    (None, None). row_number is 1-indexed and accounts for the header."""
    values = ws.get_all_values()
    for i, row in enumerate(values[1:], start=2):
        if row and row[0] and str(row[0]).strip() == str(team_id):
            width = len(HEADERS)
            row = list(row) + [""] * (width - len(row))
            return i, row[:width]
    return None, None


def set_team_problem(team_id, problem_id, problem_title):
    """Set (or change) the single problem statement a team has chosen.
    Passing problem_id=None clears the selection."""
    with _lock:
        ws = _ensure_file()
        row_num, row = _find_sheet_row(ws, team_id)
        if row_num is None:
            return None
        pid_col = HEADERS.index("Problem Statement ID") + 1
        ptitle_col = HEADERS.index("Problem Statement Title") + 1
        ws.update_cell(row_num, pid_col, problem_id if problem_id is not None else "")
        ws.update_cell(row_num, ptitle_col, problem_title or "")
        row[pid_col - 1] = problem_id if problem_id is not None else ""
        row[ptitle_col - 1] = problem_title or ""
        return _row_to_team(row)


def set_team_idea(team_id, idea):
    """Persist the team's idea / abstract text."""
    with _lock:
        ws = _ensure_file()
        row_num, row = _find_sheet_row(ws, team_id)
        if row_num is None:
            return None
        idea_col = HEADERS.index("Idea / Abstract") + 1
        cleaned = idea.strip()
        ws.update_cell(row_num, idea_col, cleaned)
        row[idea_col - 1] = cleaned
        return _row_to_team(row)


def update_team(team_id, fields):
    """Update editable fields on a team. `fields` may contain any of:
    team_name, track, college, leader_name, leader_roll_no,
    leader_email, leader_phone, idea (plain text values), and members
    (a list of {name, roll_no, email, phone} dicts that REPLACES the
    whole members list and updates the member-count column to match)."""
    with _lock:
        ws = _ensure_file()
        row_num, row = _find_sheet_row(ws, team_id)
        if row_num is None:
            return None

        col_by_field = {
            "team_name": "Team Name",
            "track": "Track",
            "college": "College / Organization",
            "leader_name": "Leader Name",
            "leader_roll_no": "Leader Roll No",
            "leader_email": "Leader Email",
            "leader_phone": "Leader Phone",
            "idea": "Idea / Abstract",
        }

        for field, header in col_by_field.items():
            if field in fields and fields[field] is not None:
                col = HEADERS.index(header) + 1
                value = str(fields[field]).strip()
                ws.update_cell(row_num, col, value)
                row[col - 1] = value

        if "members" in fields and fields["members"] is not None:
            members = fields["members"]
            count_col = HEADERS.index("Members Count") + 1
            json_col = HEADERS.index("Members JSON") + 1
            ws.update_cell(row_num, count_col, len(members))
            ws.update_cell(row_num, json_col, json.dumps(members))
            row[count_col - 1] = len(members)
            row[json_col - 1] = json.dumps(members)

        return _row_to_team(row)


def _next_team_id():
    max_id = 0
    for row in _all_rows():
        try:
            max_id = max(max_id, int(row[0]))
        except (ValueError, TypeError):
            pass
    return max_id + 1


def save_team(data):
    """Append a new team registration. Raises ValueError on duplicate
    team name."""
    with _lock:
        ws = _ensure_file()

        target = data["team_name"].strip().lower()
        for row in _all_rows():
            if row[1] and row[1].strip().lower() == target:
                raise ValueError("A team with this name has already registered.")

        members = data.get("members", [])
        team_id = _next_team_id()

        ws.append_row([
            team_id,
            data["team_name"].strip(),
            data.get("track", "").strip(),
            data.get("college", "").strip(),
            data["leader_name"].strip(),
            data.get("leader_roll_no", "").strip(),
            data["leader_email"].strip(),
            data["leader_phone"].strip(),
            len(members),
            json.dumps(members),
            data.get("idea", "").strip(),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "",   # Problem Statement ID — chosen later, via team login
            "",   # Problem Statement Title
        ], value_input_option="RAW")

        return team_id


def delete_team(team_id):
    with _lock:
        ws = _ensure_file()
        row_num, _ = _find_sheet_row(ws, team_id)
        if row_num is None:
            return False
        ws.delete_rows(row_num)
        return True


def get_dashboard_stats():
    teams = get_all_teams()
    total_teams = len(teams)
    total_participants = sum(1 + t["members_count"] for t in teams)
    by_track = {}
    for t in teams:
        key = t["track"] or "Unspecified"
        by_track[key] = by_track.get(key, 0) + 1
    return {
        "total_teams": total_teams,
        "total_participants": total_participants,
        "by_track": by_track,
    }


def export_xlsx_bytes():
    """Builds an in-memory .xlsx snapshot of the current sheet data, for
    the admin 'download teams.xlsx' button. Returns a BytesIO."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws_out = wb.active
    ws_out.title = "Registrations"
    ws_out.append(HEADERS)
    for row in _all_rows():
        ws_out.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf