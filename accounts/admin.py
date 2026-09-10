from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import PasswordResetToken, User


class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = ("email", "full_name", "role", "is_active_account", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Platform info", {"fields": ("full_name", "phone", "role", "is_active_account", "profile_image_url")}),
    )


admin.site.register(User, UserAdmin)
admin.site.register(PasswordResetToken)
