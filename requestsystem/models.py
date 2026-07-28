from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


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

    phone_code = models.CharField(max_length=6, blank=True, null=True)  # store SMS code

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
    
    # New fields
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

    # --- Choices ---
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
        ('READY', 'Ready'),
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

    # --- User & Request Info ---
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    tor_type = models.CharField(max_length=20, choices=TOR_TYPE, null=True, blank=True)
    course = models.CharField(max_length=20, choices=COURSES, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    purpose = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # --- Payment Info ---
    payment_option = models.CharField(max_length=10, choices=PAYMENT_OPTIONS, default='CASH')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='NONE')
    payment_status = models.CharField(max_length=20, choices=[("Paid", "Paid"), ("Pending", "Pending"), ("No Payment", "No Payment")], default="Pending")
    payment_receipt = models.ImageField(upload_to='payments/', null=True, blank=True)

    # --- Status & Timestamps ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    date_requested = models.DateTimeField(auto_now_add=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    date_rejected = models.DateTimeField(null=True, blank=True)
    date_released = models.DateTimeField(null=True, blank=True)
    date_processing = models.DateTimeField(null=True, blank=True)
    date_ready = models.DateTimeField(null=True, blank=True)

    # --- Notifications ---
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.get_document_type_display()} ({self.get_status_display()})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

   
@receiver(post_save, sender=DocumentRequest)
def create_document_notification(sender, instance, created, **kwargs):

    if not created:
        message = f"Your request for {instance.get_document_type_display()} is now {instance.get_status_display()}."

        DocumentNotification.objects.create(
            student=instance.user,
            document_type=instance.get_document_type_display(),
            message=message
        ) 