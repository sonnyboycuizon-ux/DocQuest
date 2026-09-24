from django.contrib import admin
from .models import DocumentRequest, Profile
from django.utils.html import format_html


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'status', 'date_requested')
    list_filter = ('status', 'document_type')


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'profile_picture_thumbnail', 'student_id', 'student_status', 'year', 'email_verified', 'phone_verified')
    list_filter = ('student_status', 'email_verified', 'phone_verified', 'year')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'student_id', 'phone_number')
    readonly_fields = ('email_verified', 'phone_verified', 'phone_code')

    def profile_picture_thumbnail(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;" />',
                obj.profile_picture.url
            )
        return format_html(
            '<div style="width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #1a365d, #2d5a87); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.8rem;">{}</div>',
            obj.user.username[:2].upper()
        )
    profile_picture_thumbnail.short_description = 'Profile Picture'
