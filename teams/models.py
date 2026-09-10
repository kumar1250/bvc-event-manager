from django.db import models

# No Django models here on purpose — registrations are stored in an Excel
# workbook (see teams/excel_utils.py). Only Django's built-in auth.User
# model (in the default sqlite3 db) is used, for admin login.
