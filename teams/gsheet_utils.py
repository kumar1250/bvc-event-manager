"""
Shared Google Sheets connection helper.

Every "Excel" module in this app (excel_utils.py, problems_excel_utils.py,
settings_utils.py) now stores its data as a tab (worksheet) inside ONE
Google Sheet, instead of a local .xlsx / .json file. This fixes the
Render free-tier issue where the local filesystem is wiped on every
restart/redeploy/spin-down — a Google Sheet lives on Google's servers,
so it survives all of that, for free, forever.

Required environment variables (set these in Render → your service →
Environment, and also in your local .env for development):

  GOOGLE_SHEET_ID
      The ID from your sheet's URL:
      https://docs.google.com/spreadsheets/d/<THIS_PART>/edit

  GOOGLE_SERVICE_ACCOUNT_JSON
      The full contents of the service-account JSON key file, pasted
      in as a single-line string. Get this from Google Cloud Console
      (see GOOGLE_SHEETS_SETUP.md for the full walkthrough).

See GOOGLE_SHEETS_SETUP.md in the project root for step-by-step setup.
"""

import json
import os
import threading

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

_lock = threading.Lock()
_client = None
_spreadsheet = None


def _load_credentials():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set. Paste the full contents "
            "of your service-account JSON key into this environment variable "
            "(see GOOGLE_SHEETS_SETUP.md)."
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON. Make sure you "
            "pasted the *entire* key file contents, on one line, with no "
            "extra quoting."
        ) from e
    return Credentials.from_service_account_info(info, scopes=_SCOPES)


def get_client():
    """Returns a cached, authorized gspread client for this process."""
    global _client
    with _lock:
        if _client is None:
            _client = gspread.authorize(_load_credentials())
        return _client


def get_spreadsheet():
    """Returns the cached Spreadsheet object (opened by GOOGLE_SHEET_ID)."""
    global _spreadsheet
    with _lock:
        if _spreadsheet is not None:
            return _spreadsheet

    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError(
            "GOOGLE_SHEET_ID is not set. Copy the ID out of your Google "
            "Sheet's URL into this environment variable "
            "(see GOOGLE_SHEETS_SETUP.md)."
        )

    client = get_client()
    try:
        ss = client.open_by_key(sheet_id)
    except gspread.exceptions.SpreadsheetNotFound as e:
        raise RuntimeError(
            "Google Sheet not found for GOOGLE_SHEET_ID. Double-check the "
            "ID, and make sure you shared the sheet with the service "
            "account's client_email as an Editor."
        ) from e

    with _lock:
        _spreadsheet = ss
    return ss


def get_or_create_worksheet(name, headers):
    """Returns the worksheet named `name` inside the spreadsheet,
    creating it (and writing the header row) if it doesn't exist yet.
    If the worksheet exists but is missing some headers (e.g. after an
    app update added a new column), the missing ones are appended so
    older sheets keep working without manual editing."""
    ss = get_spreadsheet()
    with _lock:
        try:
            ws = ss.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            ws = ss.add_worksheet(
                title=name, rows=200, cols=max(len(headers), 10)
            )
            ws.append_row(headers, value_input_option="RAW")
            return ws

        existing = ws.row_values(1)
        if not existing:
            ws.append_row(headers, value_input_option="RAW")
        else:
            missing = [h for h in headers if h not in existing]
            if missing:
                start_col = len(existing) + 1
                if ws.col_count < start_col + len(missing) - 1:
                    ws.resize(cols=start_col + len(missing) - 1)
                for i, h in enumerate(missing):
                    ws.update_cell(1, start_col + i, h)
        return ws
