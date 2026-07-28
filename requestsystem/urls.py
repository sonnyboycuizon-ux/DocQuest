from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .forms import CustomPasswordResetForm, CustomSetPasswordForm

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
   # Request password reset
path(
    'password-reset/',
    auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset.html',
        form_class=CustomPasswordResetForm
    ),
    name='password_reset',
),

# Email sent successfully
path(
    'password-reset/done/',
    auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ),
    name='password_reset_done',
),

# Link from email
path(
    'reset/<uidb64>/<token>/',
    auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        form_class=CustomSetPasswordForm
    ),
    name='password_reset_confirm',
),

# Password successfully changed
path(
    'reset/done/',
    auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ),
    name='password_reset_complete',
),
path(
    "save-student-info/",
    views.save_student_info,
    name="save_student_info"
),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('request/', views.request_document, name='request_document'),
    path('cancel/<int:request_id>/', views.cancel_request, name='cancel_request'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('payment/', views.payment_view, name='payment'),
    path('notifications/', views.notifications, name='notifications'),
    path('send-verification-code/', views.send_verification_code, name='send_verification_code'),
    path('verify-email-code/', views.verify_email_code, name='verify_email_code'),
    path('send-phone-code/', views.send_phone_code, name='send_phone_code'),
    path('verify-phone-code/', views.verify_phone_code, name='verify_phone_code'),
    path('verify-email-direct/', views.verify_email_direct, name='verify_email_direct'),
    path('request-analysis/', views.request_analysis, name='request_analysis'),
    path('manage-account/', views.manage_accounts, name='manage_account'),
    path('manage-account/update/<int:user_id>/', views.update_user_status, name='update_user_status'),
    path('manage-account/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('add-student/', views.add_student, name='add_student'),
    path('add-admin/', views.add_admin, name='add_admin'),
    path('manage-account/edit/<int:user_id>/', views.edit_user, name='edit_user'),
]