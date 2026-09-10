from django.contrib import admin
from .models import FieldOption, FormAnswer, FormField, FormSubmission, RegistrationForm


class FormFieldInline(admin.TabularInline):
    model = FormField
    extra = 0


@admin.register(RegistrationForm)
class RegistrationFormAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "status", "updated_at")
    list_filter = ("status",)
    inlines = [FormFieldInline]


admin.site.register(FormField)
admin.site.register(FieldOption)
admin.site.register(FormSubmission)
admin.site.register(FormAnswer)
