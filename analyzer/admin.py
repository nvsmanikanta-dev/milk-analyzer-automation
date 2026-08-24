from django.contrib import admin
from .models import QCEntry

@admin.register(QCEntry)
class QCEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "shift", "sample_code", "fat", "snf", "clr", "analyzer_code")
    list_filter = ("date", "shift")
    search_fields = ("sample_code", "analyzer_code")
