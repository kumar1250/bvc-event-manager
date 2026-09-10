from django.contrib import admin
from .models import Event, EventFlowStep


class EventFlowStepInline(admin.TabularInline):
    model = EventFlowStep
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "date", "venue")
    list_filter = ("category", "status")
    search_fields = ("name", "venue")
    inlines = [EventFlowStepInline]


admin.site.register(EventFlowStep)
