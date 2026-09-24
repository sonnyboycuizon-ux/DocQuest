import os
import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseNotAllowed
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count
from django.db import transaction
from django.contrib.auth.models import User
from twilio.rest import Client

from .forms import (
    UserRegisterForm,
    AdminRegistrationForm,
    DocumentRequestForm,
    ProfileUpdateForm,
)
from .models import DocumentRequest, Profile, DocumentNotification


# ==========================================
# ROLE-BASED ACCESS CONTROL HELPERS
# ==========================================

def is_super_admin(user):
    return user.is_authenticated and user.is_superuser and user.is_staff

def is_standard_admin(user):
    return user.is_authenticated and user.is_staff and not user.is_superuser

def super_admin_required(view_func):
    decorated_view_func = login_required(user_passes_test(
        lambda u: u.is_superuser and u.is_staff,
        login_url='login'
    )(view_func))
    return decorated_view_func

def standard_admin_required(view_func):
    decorated_view_func = login_required(user_passes_test(
        lambda u: u.is_staff and not u.is_superuser,
        login_url='login'
    )(view_func))
    return decorated_view_func

def any_admin_required(view_func):
    decorated_view_func = login_required(user_passes_test(
        lambda u: u.is_staff,
        login_url='login'
    )(view_func))
    return decorated_view_func


# ==========================================
# DAILY STUDENT REQUEST LIMIT HELPERS
# ==========================================

DAILY_REQUEST_LIMIT = 2


def get_today_range_ph():
    """Return (start, end) datetimes for the current calendar day in Asia/Manila."""
    now = timezone.localtime(timezone.now())
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return day_start, day_end


def get_student_daily_request_count(user):
    """Count document requests the user submitted today (Philippine timezone)."""
    if not user or not user.is_authenticated:
        return 0
    day_start, day_end = get_today_range_ph()
    return DocumentRequest.objects.filter(
        user=user,
        date_requested__gte=day_start,
        date_requested__lte=day_end,
    ).count()


def student_has_reached_daily_limit(user):
    """Return True if the given user is a student who hit the daily limit."""
    if user.is_staff:
        return False
    return get_student_daily_request_count(user) >= DAILY_REQUEST_LIMIT


def daily_limit_messages(user):
    """Return a dict with counts/messages for the templates."""
    remaining = 0
    reached = False
    if user.is_staff:
        return {
            'daily_request_count': 0,
            'daily_request_remaining': DAILY_REQUEST_LIMIT,
            'daily_limit_reached': False,
            'daily_limit_applies': False,
        }
    count = get_student_daily_request_count(user)
    remaining = max(0, DAILY_REQUEST_LIMIT - count)
    reached = count >= DAILY_REQUEST_LIMIT
    return {
        'daily_request_count': count,
        'daily_request_remaining': remaining,
        'daily_limit_reached': reached,
        'daily_limit_applies': True,
    }


# ==========================================
# PUBLIC & AUTHENTICATION VIEWS
# ==========================================

@login_required
def cancel_request(request, request_id):
    req = get_object_or_404(DocumentRequest, id=request_id, user=request.user)
    
    # Siguroha nga PENDING pa ang status bago pwede i-cancel
    if req.status == 'PENDING':
        req.delete()
        messages.success(request, f"Request #{request_id} has been canceled.")
    else:
        messages.error(request, "You can only cancel pending requests.")
        
    return redirect('dashboard')

def home(request):
    return render(request, 'requestsystem/home.html')


def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            profile, created = Profile.objects.get_or_create(user=user)
            
            # Middle initial parsing gikan sa full_name
            full_name = form.cleaned_data.get('full_name', '')
            name_parts = full_name.strip().split()
            middle_initial = ''
            if len(name_parts) > 2:
                middle_part = name_parts[1]
                if len(middle_part) > 0:
                    middle_initial = middle_part[0].upper()
            
            profile.student_id = form.cleaned_data['student_id']
            profile.phone_number = form.cleaned_data['phone_number']
            profile.middle_initial = middle_initial

            profile.save()

            messages.success(request, f'Account created successfully for {user.username}! You can now log in.')
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegisterForm()

    return render(request, 'requestsystem/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(
                    request,
                    'Your account has been suspended by the administrator. Please contact the Registrar\'s Office for assistance.'
                )
            else:
                login(request, user)

                if is_super_admin(user):
                    return redirect('admin_dashboard')
                elif is_standard_admin(user):
                    return redirect('standard_admin_dashboard')
                else:
                    return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'requestsystem/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ==========================================
# USER DASHBOARD & PROFILE VIEWS
# ==========================================

@login_required
def dashboard(request):
    user_requests = DocumentRequest.objects.filter(user=request.user).order_by('-date_requested')

    pending_count = user_requests.filter(status='PENDING').count()
    approved_count = user_requests.filter(status='APPROVED').count()
    processing_count = user_requests.filter(status='PROCESSING').count()
    ready_count = user_requests.filter(status='READY').count()
    released_count = user_requests.filter(status='RELEASED').count()
    rejected_count = user_requests.filter(status='REJECTED').count()

    notifications = user_requests[:5]

    limit_info = daily_limit_messages(request.user)

    context = {
        'requests': user_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'processing_count': processing_count,
        'ready_count': ready_count,
        'released_count': released_count,
        'rejected_count': rejected_count,
        'notifications': notifications,
        'notification_count': len(notifications),
        **limit_info,
    }

    return render(request, 'requestsystem/dashboard.html', context)


@login_required
def profile_view(request):
    return render(request, 'requestsystem/profile.html', {
        'is_admin_viewing': False,
        'target_user': request.user,
    })


@super_admin_required
def view_user_profile(request, user_id):
    """Super Admin only can view any student/user full profile page."""
    target_user = get_object_or_404(User, id=user_id)
    target_profile, _ = Profile.objects.get_or_create(user=target_user)
    return render(request, 'requestsystem/profile.html', {
        'user': target_user,
        'target_user': target_user,
        'is_admin_viewing': True,
        'admin_viewer': request.user,
    })


@login_required
def update_profile(request):
    if request.method == 'POST':
        try:
            profile, _ = Profile.objects.get_or_create(user=request.user)
        except Exception:
            profile = request.user.profile

        year = request.POST.get('year')
        if year:
            profile.year = year

        middle_initial = request.POST.get('middle_initial')
        if middle_initial is not None:
            profile.middle_initial = middle_initial

        if 'profile_picture' in request.FILES:
            uploaded_file = request.FILES['profile_picture']

            valid_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'}
            if uploaded_file.content_type and uploaded_file.content_type not in valid_types:
                return JsonResponse({
                    'success': False,
                    'message': f'Invalid file type {uploaded_file.content_type}. Please upload JPG, PNG, GIF, or WEBP.'
                }, status=400)

            if uploaded_file.size > 5 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'message': 'Image file is too large. Maximum 5MB allowed.'
                }, status=400)

            try:
                from django.core.files.images import get_image_dimensions
                from PIL import Image
                tmp_img = Image.open(uploaded_file)
                tmp_img.verify()
                uploaded_file.seek(0)
            except Exception:
                return JsonResponse({
                    'success': False,
                    'message': 'The uploaded file is corrupted or not a valid image.'
                }, status=400)

            if profile.profile_picture:
                try:
                    old_path = profile.profile_picture.path
                    if old_path and os.path.isfile(old_path):
                        os.remove(old_path)
                except Exception:
                    pass

            profile.profile_picture.save(
                f'{profile.user.username}_{profile.id}_{uploaded_file.name}',
                uploaded_file,
                save=False
            )

        profile.save()

        has_pic = bool(profile.profile_picture)
        pic_url = profile.profile_picture.url if has_pic else ''

        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully!',
            'profile_picture_url': pic_url,
            'has_profile_picture': has_pic
        })

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


@login_required
def notifications(request):
    user_requests = DocumentRequest.objects.filter(
        user=request.user
    ).order_by('-date_requested')

    context = {
        'requests': user_requests
    }

    return render(request, 'requestsystem/notifications.html', context)


# ==========================================
# VERIFICATION & PHONE / EMAIL UTILITIES
# ==========================================

@login_required
def save_student_info(request):
    if request.method != "POST":
        return JsonResponse({"success": False})

    data = json.loads(request.body)
    profile = request.user.profile

    status = data.get("status")
    student_id = data.get("student_id", "").strip()

    if status in ["student", "irregular"] and student_id == "":
        return JsonResponse({
            "success": False,
            "message": "Student ID is required."
        })

    profile.student_status = status

    if status in ["student", "irregular"]:
        profile.student_id = student_id
    else:
        profile.student_id = ""

    profile.save()

    return JsonResponse({
        "success": True,
        "message": "Information saved successfully."
    })


@login_required
def send_phone_code(request):
    data = json.loads(request.body)
    phone = data.get("phone")
    code = random.randint(100000, 999999)

    profile = request.user.profile
    profile.phone_number = phone
    profile.phone_code = code
    profile.save()

    # Send SMS via Twilio
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
    
    if account_sid and auth_token and twilio_phone:
        client = Client(account_sid, auth_token)
        try:
            message = client.messages.create(
                body=f"Your DocQuest verification code is: {code}",
                from_=twilio_phone,
                to=phone
            )
            print(f"SMS sent with SID: {message.sid}")
        except Exception as e:
            print(f"Error sending SMS: {e}")
    else:
        print("Twilio credentials not set! SMS not sent.")
        print("SMS CODE:", code)

    return JsonResponse({"message": "Verification code sent to phone"})


@login_required
def verify_phone_code(request):
    data = json.loads(request.body)
    code = data.get("code")
    profile = request.user.profile

    if str(profile.phone_code) == str(code):
        profile.phone_verified = True
        profile.save()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False})


@login_required
def send_verification_code(request):
    if request.method == 'POST':
        user_email = request.user.email
        if not user_email:
            return JsonResponse({
                'success': False,
                'message': 'Your account does not have an email address set. Please update your profile first.'
            })

        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            code = str(random.randint(100000, 999999))
            request.session['email_verification_code'] = code
            print("=" * 60)
            print("[EMAIL VERIFICATION - FALLBACK]")
            print(f"To: {user_email}")
            print(f"Verification Code: {code}")
            print("Reason: SMTP credentials not configured.")
            print("=" * 60)
            return JsonResponse({
                'success': True,
                'message': f'Code generated (SMTP not configured). Ask admin for code or check server logs: {code}'
            })

        code = str(random.randint(100000, 999999))
        request.session['email_verification_code'] = code

        email_body = (
            f"Hello {request.user.first_name or request.user.username},\n\n"
            f"Your email verification code for Document Request System is:\n\n"
            f"    {code}\n\n"
            f"This code will expire when you successfully verify or log out.\n\n"
            f"If you did not request this, ignore this email.\n\n"
            f"Thank you,\nDocument Request System"
        )

        try:
            send_mail(
                subject='Email Verification Code - Document Request System',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send verification code to {user_email}: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Could not send email now. Please try again later or contact admin.'
            })

        return JsonResponse({
            'success': True,
            'message': f'Verification code sent to {user_email}! Check your inbox (or spam folder).'
        })
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def verify_email_code(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Invalid request'})

        entered_code = (data.get('code') or '').strip()
        saved_code = request.session.get('email_verification_code')

        if not saved_code:
            return JsonResponse({
                'success': False,
                'message': 'Click "Verify Now" first to send a verification code.'
            })

        if not entered_code:
            return JsonResponse({
                'success': False,
                'message': 'Please enter the 6-digit code.'
            })

        if entered_code == saved_code:
            request.user.profile.email_verified = True
            request.user.profile.save()
            request.session.pop('email_verification_code', None)
            return JsonResponse({
                'success': True,
                'message': 'Email verified successfully!'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Incorrect code. Please check your email again.'
            })
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


# ==========================================
# DOCUMENT REQUEST & PAYMENT VIEWS
# ==========================================

def calculate_price(course, document_type, tor_type=None, quantity=1):
    if document_type == 'FORM137':
        return 100
    elif document_type == 'TRANSCRIPT':
        if tor_type == 'REGULAR':
            if course in ['BSIT', 'BSHM', 'BSENTREP']:
                return 200
            elif course in ['BSED', 'BEED']:
                return 300
        elif tor_type == 'IRREGULAR':
            return 0
    elif document_type == 'CERTIFIED TRUE COPY':
        return 15 * quantity
    elif document_type == 'DIPLOMA':
        return 250
    elif document_type in ['CERTIFICATE OF ENROLLMENT', 'CERTIFICATE WITH GRADES', 'MEDIUM OF INSTRUCTION']:
        return 50
    elif document_type == 'CARD':
        return 80
    return 0


@login_required
def request_document(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if not profile.email_verified:
        messages.error(request, "Please verify your email first before requesting documents.")
        return redirect('dashboard')

    if not request.user.is_staff and student_has_reached_daily_limit(request.user):
        messages.error(
            request,
            "Daily Request Limit Reached — You have already submitted 2 document requests today. "
            "You can request another document tomorrow."
        )
        return redirect('dashboard')

    is_irregular = profile.student_status == 'irregular'

    if request.method == "POST":
        with transaction.atomic():
            if not request.user.is_staff and student_has_reached_daily_limit(request.user):
                messages.error(
                    request,
                    "Daily Request Limit Reached — You have already submitted 2 document requests today. "
                    "Please try again tomorrow."
                )
                return redirect('dashboard')

            form = DocumentRequestForm(request.POST, request.FILES)
            if form.is_valid():
                doc_request = form.save(commit=False)

                if is_irregular and doc_request.document_type == 'TRANSCRIPT':
                    messages.error(request, "Irregular students are not allowed to request Transcript of Records online. Please contact the registrar's office.")
                    return redirect('dashboard')

                if doc_request.document_type == 'TRANSCRIPT' and doc_request.tor_type == 'IRREGULAR':
                    messages.error(request, "Irregular TOR requests cannot be processed online. Please proceed directly to the Registrar's Office.")
                    return redirect('dashboard')

                doc_request.user = request.user
                doc_request.status = 'PENDING'
                doc_request.save()
                messages.success(request, "Document request submitted successfully.")
                return redirect('dashboard')
    else:
        form = DocumentRequestForm()

    limit_info = daily_limit_messages(request.user)
    context = {
        'form': form,
        'is_irregular': is_irregular,
        **limit_info,
    }
    return render(request, 'requestsystem/request_form.html', context)


@login_required
def payment_view(request):
    if not request.session.get('face_verified'):
        return redirect('face_verification')

    document_data = request.session.get('document_data')

    if request.method == "POST":
        receipt = request.FILES.get('receipt')

        DocumentRequest.objects.create(
            user=request.user,
            document_type=document_data['document_type'],
            purpose=document_data['purpose'],
            payment_method='PNB',
            payment_receipt=receipt,
            status='PENDING'
        )

        request.session.pop('document_data', None)
        request.session.pop('face_verified', None)

        messages.success(request, "Request submitted successfully. Await admin approval.")
        return redirect('dashboard')

    return render(request, 'requestsystem/payment.html')


# ==========================================
# ADMIN & MANAGEMENT VIEWS
# ==========================================

@super_admin_required
def admin_dashboard(request):
    requests = DocumentRequest.objects.select_related('user', 'user__profile').all().order_by('-date_requested')
    courses = DocumentRequest.objects.values_list('course', flat=True).distinct()

    total_requests = requests.count()
    pending_requests = requests.filter(status='PENDING').count()
    approved_requests = requests.filter(status='APPROVED').count()
    processing_requests = requests.filter(status='PROCESSING').count()
    ready_requests = requests.filter(status='READY').count()
    released_requests = requests.filter(status='RELEASED').count()
    rejected_requests = requests.filter(status='REJECTED').count()

    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        action = request.POST.get('action')
        req = get_object_or_404(DocumentRequest, id=req_id)

        if action == 'approve':
            req.status = 'APPROVED'
            req.date_approved = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} approved successfully.")

        elif action == 'processing':
            req.status = 'PROCESSING'
            req.date_processing = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} processing successfully.")

        elif action == 'ready':
            req.status = 'READY'
            req.date_ready = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} ready successfully.")

        elif action == 'release':
            req.status = 'RELEASED'
            req.date_released = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} released successfully.")

        elif action == 'reject':
            req.status = 'REJECTED'
            req.date_rejected = timezone.now()
            messages.info(request, f"Request #{req.id} rejected.")

        elif action == 'cancel':
            req.delete()
            messages.warning(request, f"Request #{req_id} has been deleted.")
            return redirect('admin_dashboard')

        req.save()
        return redirect('admin_dashboard')

    courses = [course if course else 'N/A' for course in courses]

    context = {
        'requests': requests,
        'courses': courses,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'processing_requests': processing_requests,
        'ready_requests': ready_requests,
        'released_requests': released_requests,
        'rejected_requests': rejected_requests,
    }

    return render(request, 'requestsystem/admin_dashboard.html', context)


@standard_admin_required
def standard_admin_dashboard(request):
    requests = DocumentRequest.objects.select_related('user', 'user__profile').all().order_by('-date_requested')
    courses = DocumentRequest.objects.values_list('course', flat=True).distinct()

    total_requests = requests.count()
    pending_requests = requests.filter(status='PENDING').count()
    approved_requests = requests.filter(status='APPROVED').count()
    processing_requests = requests.filter(status='PROCESSING').count()
    ready_requests = requests.filter(status='READY').count()
    released_requests = requests.filter(status='RELEASED').count()
    rejected_requests = requests.filter(status='REJECTED').count()

    if request.method == 'POST':
        req_id = request.POST.get('req_id')
        action = request.POST.get('action')
        req = get_object_or_404(DocumentRequest, id=req_id)

        if action == 'approve':
            req.status = 'APPROVED'
            req.date_approved = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} approved successfully.")

        elif action == 'processing':
            if not request.user.is_superuser:
                messages.error(request, "You are not authorized to perform this action.")
                return redirect('standard_admin_dashboard')
            req.status = 'PROCESSING'
            req.date_processing = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} processing successfully.")

        elif action == 'ready':
            if not request.user.is_superuser:
                messages.error(request, "You are not authorized to perform this action.")
                return redirect('standard_admin_dashboard')
            req.status = 'READY'
            req.date_ready = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} ready successfully.")

        elif action == 'release':
            if not request.user.is_superuser:
                messages.error(request, "You are not authorized to perform this action.")
                return redirect('standard_admin_dashboard')
            req.status = 'RELEASED'
            req.date_released = timezone.now()
            if req.payment_option != 'CASH':
                req.payment_status = 'Paid'
            messages.success(request, f"Request #{req.id} released successfully.")

        elif action == 'reject':
            req.status = 'REJECTED'
            req.date_rejected = timezone.now()
            messages.info(request, f"Request #{req.id} rejected.")

        elif action == 'cancel':
            req.delete()
            messages.warning(request, f"Request #{req_id} has been deleted.")
            return redirect('standard_admin_dashboard')

        req.save()
        return redirect('standard_admin_dashboard')

    courses = [course if course else 'N/A' for course in courses]

    context = {
        'requests': requests,
        'courses': courses,
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'processing_requests': processing_requests,
        'ready_requests': ready_requests,
        'released_requests': released_requests,
        'rejected_requests': rejected_requests,
        'is_standard_admin': True,
    }

    return render(request, 'requestsystem/standard_admin_dashboard.html', context)


@super_admin_required
def add_admin(request):
    if request.method == "POST":
        form = AdminRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Administrator added successfully.")
            return redirect("manage_account")
    else:
        form = AdminRegistrationForm()

    return render(request, "requestsystem/add_admin.html", {"form": form})


@super_admin_required
def add_student(request):
    return render(request, 'requestsystem/add_student.html')


@super_admin_required
def manage_accounts(request):
    if request.method == 'GET':
        users = User.objects.select_related('profile').all().order_by('-date_joined')
        return render(request, 'requestsystem/manage_account.html', {'users': users})


@super_admin_required
def edit_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    profile, created = Profile.objects.get_or_create(user=target_user)

    if request.method == "POST":
        target_user.first_name = request.POST.get("first_name", "")
        target_user.last_name = request.POST.get("last_name", "")
        target_user.email = request.POST.get("email", "")
        
        target_user.is_active = 'is_suspended' not in request.POST
        if 'is_staff' in request.POST:
            target_user.is_staff = True
        
        target_user.save()

        phone_number = request.POST.get("phone_number")
        if phone_number is not None:
            profile.phone_number = phone_number
            profile.save()

        messages.success(request, f"User {target_user.username} updated successfully.")
        return redirect("manage_account")

    return render(request, "requestsystem/edit_user.html", {"target_user": target_user})


@super_admin_required
def update_user_status(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        data = json.loads(request.body)
        
        user.is_active = data.get('is_active', user.is_active)
        user.save()
        
        return JsonResponse({'status': 'success', 'message': f'Updated status for {user.username}'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


@super_admin_required
def delete_user(request, user_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)

        if user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect("manage_account")

        user.delete()
        messages.success(request, "User deleted successfully.")
        return redirect("manage_account")

    return HttpResponseNotAllowed(["POST"])


@super_admin_required
def request_analysis(request):
    requests = DocumentRequest.objects.all()

    total_requests = requests.count()
    pending_requests = requests.filter(status='PENDING').count()
    approved_requests = requests.filter(status='APPROVED').count()
    processing_requests = requests.filter(status='PROCESSING').count()
    ready_requests = requests.filter(status='READY').count()
    released_requests = requests.filter(status='RELEASED').count()
    rejected_requests = requests.filter(status='REJECTED').count()

    document_stats = requests.values('document_type').annotate(count=Count('document_type'))

    labels = [doc['document_type'] for doc in document_stats]
    data = [doc['count'] for doc in document_stats]

    context = {
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'processing_requests': processing_requests,
        'ready_requests': ready_requests,
        'released_requests': released_requests,
        'rejected_requests': rejected_requests,
        'labels': json.dumps(labels),
        'data': json.dumps(data),
    }

    return render(request, 'requestsystem/request_analysis.html', context)