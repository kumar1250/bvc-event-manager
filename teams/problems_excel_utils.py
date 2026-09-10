"""
All reads/writes to the Problem Statements "database" live here.
Mirrors excel_utils.py's pattern but uses its own worksheet tab
("Problem Statements") so it never collides with team registrations.
"""

import io
import threading
from datetime import datetime

from . import gsheet_utils

SHEET_NAME = "Problem Statements"

HEADERS = [
    "ID", "Title", "Description", "Track / Domain",
    "Difficulty", "Created At", "Updated At",
]

PROBLEM_FIELDS = [
    "id", "title", "description", "track",
    "difficulty", "created_at", "updated_at",
]

_lock = threading.Lock()


def _ensure_file():
    """Kept for backwards compatibility (views.py calls this before the
    xlsx-download endpoint). Makes sure the worksheet + headers exist,
    and returns the worksheet object."""
    return gsheet_utils.get_or_create_worksheet(SHEET_NAME, HEADERS)


def _all_rows():
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


def _row_to_problem(row):
    p = dict(zip(PROBLEM_FIELDS, row))
    p["id"] = int(p["id"]) if str(p["id"]).strip() else None
    return p


def _find_sheet_row(ws, problem_id):
    values = ws.get_all_values()
    for i, row in enumerate(values[1:], start=2):
        if row and row[0] and str(row[0]).strip() == str(problem_id):
            width = len(HEADERS)
            row = list(row) + [""] * (width - len(row))
            return i, row[:width]
    return None, None


def _next_id():
    max_id = 0
    for row in _all_rows():
        try:
            max_id = max(max_id, int(row[0]))
        except (ValueError, TypeError):
            pass
    return max_id + 1


# ---------- Read ----------

def get_all_problems(search=None, track=None, difficulty=None):
    problems = [_row_to_problem(r) for r in _all_rows()]
    result = []
    for p in problems:
        if track and track.strip().lower() != (p["track"] or "").strip().lower():
            continue
        if difficulty and difficulty.strip().lower() != (p["difficulty"] or "").strip().lower():
            continue
        if search:
            s = search.strip().lower()
            haystack = f"{p['title']} {p['description']} {p['track']}".lower()
            if s not in haystack:
                continue
        result.append(p)
    result.sort(key=lambda p: p["id"])
    result.reverse()
    return result


def get_problem(problem_id):
    for row in _all_rows():
        if row[0] and int(row[0]) == int(problem_id):
            return _row_to_problem(row)
    return None


# ---------- Create ----------

def create_problem(data):
    """Append a new problem statement."""
    with _lock:
        ws = _ensure_file()

        problem_id = _next_id()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws.append_row([
            problem_id,
            data["title"].strip(),
            data.get("description", "").strip(),
            data.get("track", "").strip(),
            data.get("difficulty", "").strip(),
            now,
            now,
        ], value_input_option="RAW")

        return problem_id


# ---------- Update ----------

def update_problem(problem_id, data):
    """Updates a row in place. Returns the updated dict, or None if
    no matching row was found."""
    with _lock:
        ws = _ensure_file()
        row_num, row = _find_sheet_row(ws, problem_id)
        if row_num is None:
            return None

        if "title" in data and data["title"]:
            row[1] = data["title"].strip()
        if "description" in data:
            row[2] = (data.get("description") or "").strip()
        if "track" in data:
            row[3] = (data.get("track") or "").strip()
        if "difficulty" in data:
            row[4] = (data.get("difficulty") or "").strip()
        row[6] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws.update(f"A{row_num}:G{row_num}", [row], value_input_option="RAW")
        return _row_to_problem(row)


# ---------- Delete ----------

def delete_problem(problem_id):
    with _lock:
        ws = _ensure_file()
        row_num, _ = _find_sheet_row(ws, problem_id)
        if row_num is None:
            return False
        ws.delete_rows(row_num)
        return True


def export_xlsx_bytes():
    """Builds an in-memory .xlsx snapshot of the current sheet data, for
    the admin 'download problem_statements.xlsx' button."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws_out = wb.active
    ws_out.title = "Problem Statements"
    ws_out.append(HEADERS)
    for row in _all_rows():
        ws_out.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
