# Google Sheets Setup Guide

Your backend now stores team registrations, problem statements, and app
settings in a **Google Sheet** instead of local `.xlsx` files. This fixes
the "data disappears after a few minutes" problem on Render's free tier —
Render wipes the local disk on every restart/redeploy/spin-down, but a
Google Sheet lives on Google's servers and survives all of that, for free,
forever.

You do **not** need to change any code. Just do the one-time setup below,
then set two environment variables.

Total time: about 5 minutes.

---

## Step 1 — Create a Google Cloud project

1. Go to https://console.cloud.google.com/
2. Click the project dropdown (top-left, next to "Google Cloud") → **New Project**
3. Name it anything, e.g. `hackathon-backend` → **Create**
4. Make sure the new project is selected in the dropdown before continuing

## Step 2 — Enable the Google Sheets and Drive APIs

1. In the search bar at the top, search for **"Google Sheets API"** → open it → click **Enable**
2. Search for **"Google Drive API"** → open it → click **Enable**
   (needed so the service account can open the sheet by ID)

## Step 3 — Create a Service Account

A service account is a "robot user" your backend logs in as — it's not
your personal Google account.

1. Search for **"Service Accounts"** in the top search bar → open it
2. Click **+ Create Service Account**
3. Name it e.g. `hackathon-sheets-bot` → **Create and Continue**
4. Role: skip this (click **Continue**), you don't need a project role
5. Click **Done**

## Step 4 — Create and download the JSON key

1. On the Service Accounts page, click the service account you just made
2. Go to the **Keys** tab → **Add Key** → **Create new key**
3. Choose **JSON** → **Create**
4. A `.json` file downloads automatically — keep it safe, you'll paste its
   contents into Render in Step 7. **Never commit this file to git or
   share it publicly** — it's a credential, like a password.
5. Open the downloaded file in a text editor. Note the `"client_email"`
   field, e.g. `hackathon-sheets-bot@hackathon-backend.iam.gserviceaccount.com`
   — you'll need it in Step 6.

## Step 5 — Create the Google Sheet

1. Go to https://sheets.google.com/ → **Blank spreadsheet**
2. Rename it to something like `Hackathon Backend Data` (the name doesn't
   matter, only the ID does)
3. Look at the URL:
   ```
   https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^ this is the ID
   ```
   Copy that ID — you'll need it in Step 7.

Leave the sheet otherwise empty — your backend automatically creates the
`Registrations`, `Problem Statements`, and `Settings` tabs (with headers)
the first time it runs.

## Step 6 — Share the Sheet with your service account

The robot user needs permission, just like sharing with a person:

1. In the Google Sheet, click **Share** (top-right)
2. Paste in the `client_email` from Step 4
3. Set its permission to **Editor**
4. Uncheck "Notify people" (it's a robot, it won't read the email) → **Share**

## Step 7 — Set the environment variables

You need two values:

- **`GOOGLE_SHEET_ID`** — the ID from Step 5
- **`GOOGLE_SERVICE_ACCOUNT_JSON`** — the *entire contents* of the JSON
  file from Step 4, pasted as one value

### On Render

1. Go to your Render dashboard → your web service → **Environment**
2. Click **Add Environment Variable** and add:
   - Key: `GOOGLE_SHEET_ID` → Value: (paste the sheet ID)
3. Add another:
   - Key: `GOOGLE_SERVICE_ACCOUNT_JSON` → Value: open the downloaded
     `.json` file, copy **everything** (the whole `{ ... }` object), and
     paste it in as the value. Render's env var fields accept multi-line
     values fine — you don't need to flatten it to one line.
4. Click **Save Changes** — Render will redeploy automatically

### For local development

Open your local `.env` file (already has placeholders added) and fill in:

```
GOOGLE_SHEET_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz
GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", "project_id": "...", "private_key": "...", ...}'
```

Wrap the JSON in single quotes so the shell/dotenv treats it as one value.

## Step 8 — Install the new dependency

Already added to `requirements.txt` (`gspread`, `google-auth`). Render
will install it automatically on the next deploy. Locally, run:

```bash
pip install -r requirements.txt
```

## Step 9 — Verify it worked

1. Redeploy on Render (or restart locally) and register a test team
   through your site
2. Open your Google Sheet in the browser — you should see a
   **Registrations** tab appear with your test team as a row
3. Wait 15+ minutes (or manually restart the Render service) and check
   again — the row should still be there. That's the fix confirmed.
4. Delete the test row from the sheet directly (or via the admin
   dashboard's delete button) when you're done testing.

---

## Troubleshooting

**"GOOGLE_SERVICE_ACCOUNT_JSON is not set"**
The env var is missing or empty on Render/locally. Re-check Step 7.

**"GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON"**
Something got cut off or extra quoting was added when pasting. Re-copy
the full `.json` file contents fresh.

**"Google Sheet not found for GOOGLE_SHEET_ID"**
Either the ID is wrong (re-check Step 5) or the sheet wasn't shared with
the service account's `client_email` (re-check Step 6) — it must be
shared as **Editor**.

**`PermissionError` / `403` on writes**
Same as above — double check the Editor share in Step 6.

**Rate limit errors under heavy simultaneous load**
Google Sheets allows 60 write requests/minute per service account by
default. Fine for normal hackathon registration traffic; if you expect a
flood of simultaneous submissions right at a deadline, consider adding
simple retry-with-backoff, or spread out the deadline messaging.

---

## What changed in the code

- `teams/gsheet_utils.py` — new shared helper that authenticates to
  Google Sheets and gets/creates worksheets
- `teams/excel_utils.py`, `teams/problems_excel_utils.py`,
  `teams/settings_utils.py` — rewritten to read/write the Google Sheet
  instead of local `.xlsx`/`.json` files. **Function names and
  signatures are unchanged**, so `views.py` needed only two small
  tweaks (the two admin "download as .xlsx" endpoints now build the
  file in-memory from the sheet instead of opening a local file)
- `requirements.txt` — added `gspread` and `google-auth`
- `.env` — added placeholders for the two new env vars
- `core/settings.py` — removed the now-unused local file path constants

Nothing about your API endpoints, request/response shapes, or frontend
changed — this is purely a storage-layer swap.
