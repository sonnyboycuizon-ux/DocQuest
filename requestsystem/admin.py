from django.contrib import admin
from .models import DocumentRequest

@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'status', 'date_requested')
    list_filter = ('status', 'document_type')
