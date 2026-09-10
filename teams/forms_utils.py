"""
All reads/writes for the "Dynamic Forms" feature live here.

Two worksheet tabs are used (same pattern as excel_utils.py /
problems_excel_utils.py):

  "Forms"          — one row per form the admin has built. The field
                      list itself (label, type, required, unique, ...)
                      is stored as a JSON blob in one cell, since the
                      number/shape of fields is arbitrary — just like
                      a Google Form.

  "Form Responses" — one row per submission, tagged with which form it
                      belongs to. The submitted answers are stored as
                      a JSON blob keyed by field id, again because the
                      shape depends entirely on that form's fields.

FIELD SCHEMA (each item in a form's "fields" list):
{
    "id":        "f_ab12cd34"   # stable key used in submitted answers
    "label":     "College Email",
    "type":      "text" | "textarea" | "number" | "email" | "phone" |
                 "date" | "time" | "dropdown" | "radio" | "checkbox" |
                 "file",
    "required":  bool,
    "unique":    bool,   # <-- the "unique value" option: no two
                          #     responses may share this field's value
    "options":   [...],  # for dropdown / radio / checkbox
    "placeholder": "optional hint text",
    "help_text":   "optional description under the label",
}
"""

import io
import json
import threading
import uuid
from datetime import datetime

from . import gsheet_utils

FORMS_SHEET = "Forms"
FORMS_HEADERS = [
    "Form ID", "Title", "Description", "Fields JSON",
    "Is Active", "Created At", "Updated At",
]
FORM_FIELDS = [
    "id", "title", "description", "fields_json",
    "is_active", "created_at", "updated_at",
]

RESPONSES_SHEET = "Form Responses"
RESPONSES_HEADERS = ["Response ID", "Form ID", "Data JSON", "Submitted At"]
RESPONSE_FIELDS = ["id", "form_id", "data_json", "submitted_at"]

CHOICE_TYPES = {"dropdown", "radio"}
MULTI_CHOICE_TYPES = {"checkbox"}
VALID_FIELD_TYPES = {
    "text", "textarea", "number", "email", "phone",
    "date", "time", "dropdown", "radio", "checkbox", "file",
}

_lock = threading.Lock()


# ---------- low-level sheet helpers ----------

def _forms_ws():
    return gsheet_utils.get_or_create_worksheet(FORMS_SHEET, FORMS_HEADERS)


def _responses_ws():
    return gsheet_utils.get_or_create_worksheet(RESPONSES_SHEET, RESPONSES_HEADERS)


def _all_rows(ws, headers):
    values = ws.get_all_values()[1:]
    rows = []
    width = len(headers)
    for row in values:
        if not row or not (row[0] or "").strip():
            continue
        row = list(row) + [""] * (width - len(row))
        rows.append(row[:width])
    return rows


def _find_row(ws, headers, row_id):
    values = ws.get_all_values()
    for i, row in enumerate(values[1:], start=2):
        if row and row[0] and str(row[0]).strip() == str(row_id):
            width = len(headers)
            row = list(row) + [""] * (width - len(row))
            return i, row[:width]
    return None, None


def _next_id(ws, headers):
    max_id = 0
    for row in _all_rows(ws, headers):
        try:
            max_id = max(max_id, int(row[0]))
        except (ValueError, TypeError):
            pass
    return max_id + 1


# ---------- field id helpers ----------

def _assign_field_ids(fields):
    """Makes sure every field has a stable, unique id. Keeps ids the
    admin already supplied (so editing a form doesn't orphan existing
    responses' answers) and generates short ones for new fields."""
    seen = set()
    out = []
    for field in fields:
        field = dict(field)
        fid = (field.get("id") or "").strip()
        if not fid or fid in seen:
            fid = f"f_{uuid.uuid4().hex[:8]}"
        field["id"] = fid
        seen.add(fid)
        out.append(field)
    return out


# ---------- row <-> dict ----------

def _row_to_form(row, with_response_count=False):
    f = dict(zip(FORM_FIELDS, row))
    f["id"] = int(f["id"]) if str(f["id"]).strip() else None
    try:
        f["fields"] = json.loads(f.pop("fields_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        f["fields"] = []
        f.pop("fields_json", None)
    f["is_active"] = str(f.get("is_active", "")).strip().lower() in ("true", "1", "yes")
    if with_response_count:
        f["response_count"] = sum(
            1 for r in _all_rows(_responses_ws(), RESPONSES_HEADERS)
            if r[1] and str(r[1]) == str(f["id"])
        )
    return f


def _row_to_response(row):
    r = dict(zip(RESPONSE_FIELDS, row))
    r["id"] = int(r["id"]) if str(r["id"]).strip() else None
    r["form_id"] = int(r["form_id"]) if str(r["form_id"]).strip() else None
    try:
        r["data"] = json.loads(r.pop("data_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        r["data"] = {}
        r.pop("data_json", None)
    return r


# ---------- Forms: CRUD ----------

def get_all_forms(search=None):
    ws = _forms_ws()
    forms = [_row_to_form(r, with_response_count=True) for r in _all_rows(ws, FORMS_HEADERS)]
    if search:
        s = search.strip().lower()
        forms = [f for f in forms if s in f["title"].lower() or s in (f["description"] or "").lower()]
    forms.sort(key=lambda f: f["id"])
    forms.reverse()
    return forms


def get_form(form_id):
    ws = _forms_ws()
    _, row = _find_row(ws, FORMS_HEADERS, form_id)
    if row is None:
        return None
    return _row_to_form(row, with_response_count=True)


def get_form_public(form_id):
    """Only returns the form if it's currently accepting responses."""
    form = get_form(form_id)
    if form is None or not form["is_active"]:
        return None
    return form


def create_form(data):
    with _lock:
        ws = _forms_ws()
        form_id = _next_id(ws, FORMS_HEADERS)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields = _assign_field_ids(data.get("fields", []))

        ws.append_row([
            form_id,
            data["title"].strip(),
            (data.get("description") or "").strip(),
            json.dumps(fields),
            "True" if data.get("is_active", True) else "False",
            now,
            now,
        ], value_input_option="RAW")

        return form_id


def update_form(form_id, data):
    with _lock:
        ws = _forms_ws()
        row_num, row = _find_row(ws, FORMS_HEADERS, form_id)
        if row_num is None:
            return None

        if "title" in data and data["title"]:
            row[1] = data["title"].strip()
        if "description" in data:
            row[2] = (data.get("description") or "").strip()
        if "fields" in data and data["fields"] is not None:
            # Preserve ids for fields the admin kept, so past responses
            # still line up with the right field.
            row[3] = json.dumps(_assign_field_ids(data["fields"]))
        if "is_active" in data and data["is_active"] is not None:
            row[4] = "True" if data["is_active"] else "False"
        row[6] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        ws.update(f"A{row_num}:G{row_num}", [row], value_input_option="RAW")
        return _row_to_form(row, with_response_count=True)


def delete_form(form_id):
    with _lock:
        ws = _forms_ws()
        row_num, _ = _find_row(ws, FORMS_HEADERS, form_id)
        if row_num is None:
            return False
        ws.delete_rows(row_num)

        # Clean up its responses too, so they don't pile up orphaned.
        rws = _responses_ws()
        values = rws.get_all_values()
        rows_to_delete = [
            i for i, row in enumerate(values[1:], start=2)
            if row and row[1] and str(row[1]) == str(form_id)
        ]
        for i in reversed(rows_to_delete):
            rws.delete_rows(i)
        return True


# ---------- Responses: validation ----------

def _is_empty(value):
    return value is None or value == "" or value == []


def validate_response_data(form, data):
    """Checks submitted `data` (dict of field_id -> raw value) against
    the form's field definitions. Returns (cleaned_data, errors) where
    errors is a dict of field_id -> message; empty means valid."""
    cleaned = {}
    errors = {}

    for field in form.get("fields", []):
        fid = field["id"]
        label = field.get("label", fid)
        ftype = field.get("type", "text")
        required = bool(field.get("required"))
        options = field.get("options") or []
        raw = data.get(fid)

        if required and _is_empty(raw):
            errors[fid] = f"'{label}' is required."
            continue
        if _is_empty(raw):
            cleaned[fid] = [] if ftype in MULTI_CHOICE_TYPES else ""
            continue

        if ftype in CHOICE_TYPES:
            if raw not in options:
                errors[fid] = f"'{label}' must be one of the given options."
                continue
            cleaned[fid] = raw

        elif ftype in MULTI_CHOICE_TYPES:
            if not isinstance(raw, list) or any(v not in options for v in raw):
                errors[fid] = f"'{label}' must be a list of the given options."
                continue
            cleaned[fid] = raw

        elif ftype == "email":
            value = str(raw).strip()
            local, _, domain = value.partition("@")
            if not local or "." not in domain:
                errors[fid] = f"'{label}' must be a valid email address."
                continue
            cleaned[fid] = value

        elif ftype == "number":
            try:
                num = float(raw)
                cleaned[fid] = int(num) if num.is_integer() else num
            except (TypeError, ValueError):
                errors[fid] = f"'{label}' must be a number."
                continue

        else:  # text, textarea, phone, date, time, file
            cleaned[fid] = str(raw).strip()

    return cleaned, errors


def _values_equal(a, b):
    if isinstance(a, list) or isinstance(b, list):
        norm = lambda v: sorted(str(x).strip().lower() for x in (v or []))
        return norm(a) == norm(b)
    return str(a).strip().lower() == str(b).strip().lower()


def check_unique_fields(form, cleaned_data, exclude_response_id=None):
    """Returns a dict of field_id -> error message for any field marked
    `unique` whose submitted value already exists in another response
    to this form."""
    unique_fields = [f for f in form.get("fields", []) if f.get("unique")]
    if not unique_fields:
        return {}

    existing = get_responses(form["id"])
    errors = {}
    for field in unique_fields:
        fid = field["id"]
        value = cleaned_data.get(fid)
        if _is_empty(value):
            continue
        for resp in existing:
            if exclude_response_id is not None and resp["id"] == exclude_response_id:
                continue
            other = resp["data"].get(fid)
            if not _is_empty(other) and _values_equal(value, other):
                errors[fid] = (
                    f"'{field.get('label', fid)}' must be unique — "
                    f"this value has already been submitted."
                )
                break
    return errors


# ---------- Responses: CRUD ----------

def get_responses(form_id):
    ws = _responses_ws()
    responses = [
        _row_to_response(r) for r in _all_rows(ws, RESPONSES_HEADERS)
        if r[1] and str(r[1]) == str(form_id)
    ]
    responses.sort(key=lambda r: r["id"])
    return responses


def submit_response(form, cleaned_data):
    with _lock:
        ws = _responses_ws()
        response_id = _next_id(ws, RESPONSES_HEADERS)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([
            response_id,
            form["id"],
            json.dumps(cleaned_data),
            now,
        ], value_input_option="RAW")
        return response_id


def delete_response(form_id, response_id):
    with _lock:
        ws = _responses_ws()
        row_num, row = _find_row(ws, RESPONSES_HEADERS, response_id)
        if row_num is None or not row[1] or str(row[1]) != str(form_id):
            return False
        ws.delete_rows(row_num)
        return True


def export_responses_xlsx_bytes(form):
    """Builds an in-memory .xlsx with one column per field (using field
    labels as headers) plus Response ID / Submitted At."""
    import openpyxl

    fields = form.get("fields", [])
    headers = ["Response ID"] + [f["label"] for f in fields] + ["Submitted At"]

    wb = openpyxl.Workbook()
    ws_out = wb.active
    ws_out.title = (form.get("title") or "Responses")[:31] or "Responses"
    ws_out.append(headers)

    for resp in get_responses(form["id"]):
        row = [resp["id"]]
        for field in fields:
            value = resp["data"].get(field["id"], "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            row.append(value)
        row.append(resp["submitted_at"])
        ws_out.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
