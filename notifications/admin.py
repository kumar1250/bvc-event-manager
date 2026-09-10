from django.contrib import admin
from .models import Notification, EmailLog

admin.site.register(Notification)
admin.site.register(EmailLog)
