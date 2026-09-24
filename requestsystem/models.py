from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


class DocumentNotification(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=100)
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.document_type}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)

    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)

    phone_code = models.CharField(max_length=6, blank=True, null=True)

    student_id = models.CharField(max_length=30, blank=True, null=True)

    STATUS_CHOICES = [
        ('student', 'Current Student'),
        ('irregular', 'Irregular Student'),
        ('graduated', 'Graduated'),
    ]

    student_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='student'
    )

    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    YEAR_CHOICES = [
            ('1st Year', '1st Year'),
            ('2nd Year', '2nd Year'),
            ('3rd Year', '3rd Year'),
            ('4th Year', '4th Year'),
            ('Graduated', 'Graduated'),
        ]

    year = models.CharField(
        max_length=20,
        choices=YEAR_CHOICES,
        blank=True,
        null=True
    )

    MIDDLE_INITIAL_CHOICES = [
        ('N/A', 'N/A'),
    ] + [(chr(ord('A') + i), chr(ord('A') + i) + '.') for i in range(26)]

    middle_initial = models.CharField(
        max_length=3,
        choices=MIDDLE_INITIAL_CHOICES,
        default='N/A',
        blank=True,
        null=True
    )

    def __str__(self):
        return self.user.username


class DocumentRequest(models.Model):

    DOCUMENT_TYPES = [
        ('FORM137', 'Form 137'),
        ('TRANSCRIPT', 'Transcript of Records (TOR)'),
        ('CERTIFIED TRUE COPY', 'Certified True Copy'),
        ('DIPLOMA', 'Diploma'),
        ('CERTIFICATE OF ENROLLMENT', 'Certificate of Enrollment'),
        ('CERTIFICATE WITH GRADES', 'Certificate with Grades'),
        ('MEDIUM OF INSTRUCTION', 'Medium of Instruction (MOT)'),
        ('CARD', 'Card'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PROCESSING', 'Processing'),
        ('READY', 'Ready for Pickup'),
        ('REJECTED', 'Rejected'),
        ('RELEASED', 'Released'),
        ('CANCEL', 'Cancel'),
    ]

    TOR_TYPE = [
        ('REGULAR','Regular'),
        ('IRREGULAR','Irregular'),
    ]

    COURSES = [
        ('BSHM','BSHM'),
        ('BSIT','BSIT'),
        ('BEED','BEED'),
        ('BSED','BSED'),
        ('BSENTREP','BSENTREP'),
    ]

    PAYMENT_OPTIONS = [
        ('CASH','Pay as Cash'),
        ('BANK','Bank Payment'),
    ]

    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('BANK', 'Bank Transfer'),
        ('ONLINE', 'Online Payment'),
        ('NONE', 'No Payment'),
    ]

    EMAIL_NOTIFY_STATUSES = {'APPROVED', 'PROCESSING', 'READY', 'RELEASED'}

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    tor_type = models.CharField(max_length=20, choices=TOR_TYPE, null=True, blank=True)
    course = models.CharField(max_length=20, choices=COURSES, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    purpose = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    payment_option = models.CharField(max_length=10, choices=PAYMENT_OPTIONS, default='CASH')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='NONE')
    payment_status = models.CharField(max_length=20, choices=[("Paid", "Paid"), ("Pending", "Pending"), ("No Payment", "No Payment")], default="Pending")
    payment_receipt = models.ImageField(upload_to='payments/', null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    date_requested = models.DateTimeField(auto_now_add=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    date_rejected = models.DateTimeField(null=True, blank=True)
    date_released = models.DateTimeField(null=True, blank=True)
    date_processing = models.DateTimeField(null=True, blank=True)
    date_ready = models.DateTimeField(null=True, blank=True)

    is_read = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"{self.user.username} - {self.get_document_type_display()} ({self.get_status_display()})"


def format_ph_time(dt):
    if not dt:
        return 'N/A'
    local_dt = timezone.localtime(dt)
    return local_dt.strftime('%B %d, %Y %I:%M %p')


def send_document_status_email(doc_request):
    student_email = doc_request.user.email
    if not student_email:
        return

    document_name = doc_request.get_document_type_display()
    status_display = doc_request.get_status_display()
    student_name = f"{doc_request.user.first_name} {doc_request.user.last_name}".strip() or doc_request.user.username

    status_messages = {
        'APPROVED': {
            'subject': f'Document Request #{doc_request.id} - {document_name}: Approved',
            'body': (
                f"Dear {student_name},\n\n"
                f"Your document request for {document_name} (Request #{doc_request.id}) has been APPROVED.\n\n"
                f"Document: {document_name}\n"
                f"Status: Approved\n"
                f"Date Approved: {format_ph_time(doc_request.date_approved)}\n\n"
                f"Your document is now being processed. You will receive another notification once it is ready for pickup.\n\n"
                f"Thank you,\n"
                f"Document Request System"
            )
        },
        'PROCESSING': {
            'subject': f'Document Request #{doc_request.id} - {document_name}: Now Processing',
            'body': (
                f"Dear {student_name},\n\n"
                f"Your document request for {document_name} (Request #{doc_request.id}) is now PROCESSING.\n\n"
                f"Document: {document_name}\n"
                f"Status: Processing / Releasing\n"
                f"Date Processing Started: {format_ph_time(doc_request.date_processing)}\n\n"
                f"We are currently preparing your document. You will be notified once it is ready for pickup.\n\n"
                f"Thank you for your patience,\n"
                f"Document Request System"
            )
        },
        'READY': {
            'subject': f'Document Request #{doc_request.id} - {document_name}: Ready for Pickup',
            'body': (
                f"Dear {student_name},\n\n"
                f"Your document request for {document_name} (Request #{doc_request.id}) is now READY FOR PICKUP!\n\n"
                f"Document: {document_name}\n"
                f"Status: Ready for Pickup\n"
                f"Date Ready: {format_ph_time(doc_request.date_ready)}\n\n"
                f"Please proceed to the Registrar's Office to claim your document. Don't forget to bring your Student ID and the request reference number.\n\n"
                f"Request Reference: #{doc_request.id}\n\n"
                f"Congratulations!\n"
                f"Document Request System"
            )
        },
        'RELEASED': {
            'subject': f'Document Request #{doc_request.id} - {document_name}: Released',
            'body': (
                f"Dear {student_name},\n\n"
                f"Your document request for {document_name} (Request #{doc_request.id}) has been RELEASED.\n\n"
                f"Document: {document_name}\n"
                f"Status: Released\n"
                f"Date Released: {format_ph_time(doc_request.date_released)}\n\n"
                f"Your document has been successfully released. If you have any concerns, please contact the Registrar's Office.\n\n"
                f"Thank you for using our service!\n"
                f"Document Request System"
            )
        },
    }

    email_info = status_messages.get(doc_request.status)
    if not email_info:
        return

    try:
        send_mail(
            subject=email_info['subject'],
            message=email_info['body'],
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student_email],
            fail_silently=True,
        )
    except Exception:
        pass


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    Profile.objects.get_or_create(user=instance)
    instance.profile.save()


@receiver(post_save, sender=DocumentRequest)
def create_document_notification(sender, instance, created, **kwargs):
    status_changed = False
    if hasattr(instance, '_original_status'):
        status_changed = instance._original_status != instance.status

    if created:
        return

    if status_changed:
        message = f"Your request for {instance.get_document_type_display()} is now {instance.get_status_display()}."

        DocumentNotification.objects.create(
            student=instance.user,
            document_type=instance.get_document_type_display(),
            message=message
        )

        if instance.status in DocumentRequest.EMAIL_NOTIFY_STATUSES:
            send_document_status_email(instance)