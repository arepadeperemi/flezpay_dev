from flezpay.storage import AvatarStorage
from flezpay.storage import ProductStorage
from flezpay.storage import BrandStorage, ProductStorage, AvatarStorage, LivechatStorage
import datetime
import os
import uuid
from email.policy import default

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from time import time
from cryptography.fernet import InvalidToken
from api.external.encryption import Encryption

cipher = Encryption()


def validate_image(image):
    file_size = image.size
    megabyte_limit = 20.0
    if file_size > megabyte_limit * 1024 * 1024:
        raise ValidationError(f"Max file size is {megabyte_limit}MB")

    valid_extensions = ['image/jpeg', 'image/png', 'image/jpg']
    if image.content_type not in valid_extensions:
        raise ValidationError("Unsupported file type. Only PNG, JPG and JPEG are allowed.")


def upload(instance, filename, url):
    if not filename:
        return None

    # Allowed formats for images, documents, and videos
    allowed_extensions = ['png', 'jpg', 'jpeg', 'webp', 'svg', 'pdf', 'mp4', 'mov', 'avi', 'mkv', 'webm']
    ext = filename.split('.')[-1].lower()

    if ext not in allowed_extensions:
        raise ValidationError(
            f"Invalid file format. Allowed formats are: {', '.join(allowed_extensions)}"
        )

    unique_name = f"{uuid.uuid4()}.{ext}"
    return os.path.join('upload', url, unique_name)


def upload_to(instance, filename):
    return upload(instance, filename, 'docs/user/verification/protected')

def user_upload_to(instance, filename):
    return upload(instance, filename, 'docs/user')

def crypto_upload_to(instance, filename):
    return upload(instance, filename, 'crypto_assets')

def default_store_operating_hours():
    return {"always_open": True}

now = int(time())

class UserSecureManager(BaseUserManager):
    def create_user(self, user_email, password=None, **extra_fields):
        if not user_email:
            raise ValueError('The Email field must be set')
        user_email = self.normalize_email(user_email)
        user = self.model(user_email=user_email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, user_email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(user_email, password, **extra_fields)

class UserSecure(AbstractBaseUser, PermissionsMixin):
    uniq_id = models.BigAutoField(primary_key=True)
    user_email = models.EmailField(max_length=100, unique=True, error_messages={
        'unique': 'Email already exists with us.',
    })
    # 'password' field is provided by AbstractBaseUser
    user_type = models.CharField(max_length=20, choices=[('business', 'Business'), ('individual', 'Individual'), ('admin', 'Admin'), ('manager', 'Manager'), ('staff', 'Staff')], default='individual')
    business_owner = models.ForeignKey('self', on_delete=models.CASCADE, related_name='staff_members', null=True, blank=True)
    account_type = models.CharField(max_length=100, null=True, blank=True) # Keeping for legacy if needed, but we'll use user_type
    is_social_account = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    kyc_verified = models.BooleanField(default=False)
    kyb_verified = models.BooleanField(default=False)
    user_id = models.CharField(max_length=100, unique=True, db_index=True)
    date_created = models.BigIntegerField(default=now)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) # Required for admin access
    user_ip = models.CharField(max_length=45, null=True, blank=True)
    user_phone = models.BigIntegerField(null=True, blank=True, db_index=True)
    is_superuser = models.BooleanField(default=False)
    paystack_user_id = models.CharField(default='', null=True, max_length=100, blank=True)
    admin_permissions = models.JSONField(default=dict, blank=True, null=True)
    admin_settings = models.JSONField(default=dict, blank=True, null=True)
    privacy_settings = models.JSONField(default=dict, blank=True, null=True)
    two_factor_secret = models.CharField(max_length=100, null=True, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    transfers_disabled = models.BooleanField(default=False)
    withdrawals_disabled = models.BooleanField(default=False)

    objects = UserSecureManager()

    USERNAME_FIELD = 'user_email'
    REQUIRED_FIELDS = ['user_id']

    def __str__(self):
        return self.user_email

    @property
    def email(self):
        return self.user_email

    @property
    def username(self):
        return self.user_email

    def get_full_name(self):
        try:
            details = self.details.first() if hasattr(self, 'details') else None
            if details:
                full = f"{details.first_name or ''} {details.last_name or ''}".strip()
                if full:
                    return full
        except Exception:
            pass
        return self.user_email

    def get_short_name(self):
        try:
            details = self.details.first() if hasattr(self, 'details') else None
            if details and details.first_name:
                return details.first_name
        except Exception:
            pass
        return self.user_email

    @property
    def id(self):
        return self.uniq_id

    @property
    def manager_record(self):
        if self.user_type == 'manager':
            from api.models import UserManagers
            return UserManagers.objects.filter(manager_email__iexact=self.user_email).first()
        return None

    @property
    def can_manage_finances(self):
        if self.user_type == 'manager':
            mgr = self.manager_record
            return bool(mgr and mgr.manage_finances)
        return True

    @property
    def can_manage_payroll(self):
        if self.user_type == 'manager':
            mgr = self.manager_record
            return bool(mgr and mgr.manage_payroll)
        return True

    def __str__(self):
        return self.user_id


class UserDetails(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='details')
    user_country = models.CharField(max_length=100, null=False)
    user_timezone = models.CharField(max_length=100, default='Africa/Lagos')
    currency = models.CharField(max_length=10, default='NGN')
    user_avatar = models.ImageField(storage=AvatarStorage(), upload_to="", default='upload/docs/user/placeholder_avi.png', null=True)
    first_name = models.CharField(max_length=100, default=None, null=False)
    last_name = models.CharField(max_length=100, default=None, null=False)
    job_title = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    pos_access = models.BooleanField(default=True)
    can_apply_discounts = models.BooleanField(default=False)
    can_process_refunds = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    has_claimed_promo = models.BooleanField(default=False)
    meta_page_connected = models.BooleanField(default=False)
    meta_access_token = models.CharField(max_length=500, null=True, blank=True)
    meta_page_id = models.CharField(max_length=255, null=True, blank=True)
    meta_page_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.user.user_id})"

class AccountStatusHistory(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='status_history')
    admin_user = models.ForeignKey(UserSecure, on_delete=models.SET_NULL, null=True, related_name='admin_status_actions')
    status_is_active = models.BooleanField(default=True)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Status: {self.status_is_active} for {self.user.user_id} by {self.admin_user.user_id if self.admin_user else 'System'}"


class AuthenticationPin(models.Model):
    user_phone = models.CharField(max_length=100, default=None)
    user_pin = models.BigIntegerField(default=None)
    user_pin_type = models.CharField(max_length=100, default=None, null=True, blank=True)
    create_time = models.BigIntegerField(default=now)


class UserTrxPin(models.Model):
    user_details = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='transaction_pins')
    account_pin = models.CharField(max_length=100, default=None)

    def __str__(self):
        return f"Transaction PIN for {self.user_details}"


class UserTransactions(models.Model):
    TRX_TYPES = [
        ('credit', 'Credit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('payment', 'Payment'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    user = models.ForeignKey('UserSecure', on_delete=models.CASCADE, related_name='transactions')
    trx_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    trx_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    trx_amount = models.FloatField(null=False, blank=False)
    trx_currency = models.CharField(max_length=4, blank=False, null=False)
    trx_type = models.CharField(max_length=10, null=False, blank=False, choices=TRX_TYPES)
    description = models.TextField(null=True, blank=True)
    user_collection_id = models.CharField(max_length=100, default=None)
    destination_id = models.CharField(max_length=100, default=None)
    trx_source = models.CharField(max_length=100, default='0', blank=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transaction {self.trx_id}: {self.trx_amount} {self.trx_currency} ({self.trx_type})"

class TransactionBackup(models.Model):
    trx_id = models.UUIDField(default=None, blank=False, unique=True)
    trx_amount = models.FloatField(null=False, blank=False)
    trx_uniq = models.ForeignKey(UserTransactions, on_delete=models.CASCADE, related_name='transaction_backup')
    sender = models.CharField(default=None, max_length=100)
    recipient = models.CharField(default=None, max_length=100)
    trx_currency = models.CharField(max_length=100, blank=False, null=False, default='NGN')
    timestamp = models.DateTimeField(auto_now_add=True)

class AskedQuestions(models.Model):
    uniq_id = models.BigAutoField(primary_key=True, default=None)
    question = models.CharField(max_length=100, default=None)
    answer = models.TextField(default=None)

    def __str__(self):
        return self.answer


class BlogCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class HelpCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class BlogPost(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    summary = models.TextField(blank=True, null=True)
    content = models.TextField()
    category = models.ForeignKey(BlogCategory, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    is_published = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class BlogComment(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=150)
    email = models.EmailField()
    comment = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    is_approved = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Comment by {self.name} on {self.post.title}"


class HelpArticle(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    content = models.TextField()
    category = models.ForeignKey(HelpCategory, on_delete=models.SET_NULL, null=True, blank=True)
    youtube_video_url = models.URLField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class UserSupport(models.Model):
    uniq_id = models.BigAutoField(primary_key=True, default=None)
    support_phone = models.CharField(max_length=100, default=None)
    support_description = models.CharField(max_length=100, default=None)
    support_email = models.CharField(max_length=100, default=None)

    def __str__(self):
        return f"{self.support_phone}"


class UserVerificationDetails(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='verification')
    verification_type = models.CharField(max_length=100, null=True, blank=True, default=None)
    verification_id = models.CharField(max_length=100, null=True, blank=True, default=None)
    account_type = models.CharField(max_length=100, null=True, blank=True, default=None)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    user_address = models.CharField(max_length=100, blank=True, null=True)  # Optional
    proof_of_address = models.FileField(upload_to=upload_to, blank=True, null=True)  # Optional (Image or PDF)
    user_image = models.FileField(upload_to=upload_to, blank=True, null=True)  # Optional (Image or PDF)
    user_video = models.FileField(upload_to=upload_to, blank=True, null=True)
    driver_licence = models.FileField(upload_to=upload_to, blank=True, null=True)  # Optional (Image or PDF)
    legal_id = models.CharField(max_length=100, null=True, blank=True)  # Optional
    verification_status = models.CharField(max_length=100, null=True, blank=True, default='0')  # Optional
    reason = models.TextField(null=True, blank=True)  # Optional reason for approval/rejection
    provider_reference = models.CharField(max_length=150, null=True, blank=True, default=None)  # Myaza verificationId
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'verification_type')]

    def __str__(self):
        return self.account_type


class UserItems(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='items')
    item_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    item_name = models.TextField(null=False, blank=False)
    item_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    item_buy_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    item_quantity = models.IntegerField(null=True, blank=True)
    item_description = models.TextField(default=None, blank=True, null=True)
    item_weight = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    item_weight_unit = models.CharField(max_length=2, null=True, blank=True, default='kg', choices=[('kg', 'Kilogram'), ('g', 'Gram')])
    item_serial_number = models.TextField(max_length=100, null=True, blank=True)
    item_expiry = models.TextField(max_length=100, null=True, blank=True)
    item_category = models.TextField(max_length=100, default=None, blank=True, null=True)
    item_department = models.TextField(max_length=100, default=None, blank=True, null=True)
    item_colors = models.TextField(null=True, blank=True)
    color_name = models.CharField(max_length=100, null=True, blank=True)
    color_hex = models.CharField(max_length=7, null=True, blank=True)
    is_promo = models.BooleanField(default=False)
    promo_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    in_store = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    last_adjusted_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    last_adjusted_date = models.DateTimeField(default=None, blank=True, null=True)

    # Digital Product / E-Book fields
    is_digital = models.BooleanField(default=False)
    digital_file = models.FileField(upload_to='docs/user/digital_products/', null=True, blank=True)
    digital_file_name = models.CharField(max_length=255, null=True, blank=True)
    digital_file_size = models.CharField(max_length=50, null=True, blank=True)
    digital_format = models.CharField(max_length=50, null=True, blank=True)
    book_author = models.CharField(max_length=255, null=True, blank=True)
    book_publisher = models.CharField(max_length=255, null=True, blank=True)
    book_publication_date = models.CharField(max_length=100, null=True, blank=True)
    book_isbn = models.CharField(max_length=100, null=True, blank=True)
    book_pages = models.IntegerField(null=True, blank=True)
    book_language = models.CharField(max_length=100, null=True, blank=True, default='English')
    book_edition = models.CharField(max_length=100, null=True, blank=True)
    book_reading_time = models.CharField(max_length=100, null=True, blank=True)
    book_sample_file = models.FileField(upload_to='docs/user/book_samples/', null=True, blank=True)
    book_sample_text = models.TextField(null=True, blank=True)
    book_series = models.CharField(max_length=255, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    @property
    def has_color_variants(self):
        return self.variants.filter(color_hex__isnull=False).exclude(color_hex='').exists()

    @property
    def has_custom_variants(self):
        return self.variants.filter(models.Q(color_hex__isnull=True) | models.Q(color_hex='') | models.Q(variant_name='custom')).exists()

    @property
    def color_variants(self):
        return self.variants.filter(color_hex__isnull=False).exclude(color_hex='').exclude(variant_name='custom')

    @property
    def custom_variants(self):
        return self.variants.filter(models.Q(color_hex__isnull=True) | models.Q(color_hex='') | models.Q(variant_name='custom'))

    @property
    def has_variants(self):
        return self.variants.exists()

    @property
    def promo_percentage(self):
        return self.promo_amount

    @promo_percentage.setter
    def promo_percentage(self, value):
        self.promo_amount = value


class ProductVariant(models.Model):
    product = models.ForeignKey(UserItems, on_delete=models.CASCADE, related_name='variants')
    variant_name = models.CharField(max_length=50, default='color')
    sku = models.CharField(max_length=100, null=True, blank=True)
    image = models.ImageField(upload_to='docs/user/products/variants/', null=True, blank=True)
    color_name = models.CharField(max_length=100, null=True, blank=True)
    color_hex = models.CharField(max_length=7, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    material = models.CharField(max_length=100, null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'variant_name', 'color_name', 'size')

    def __str__(self):
        desc = self.color_name or self.size or self.variant_name
        return f"{self.product.item_name} - {desc}"

    @property
    def discounted_price(self):
        if hasattr(self, '_discounted_price'):
            return self._discounted_price
        pct = getattr(self.product, 'discount_percentage', None)
        if not pct and hasattr(self.product, 'user'):
            try:
                business = getattr(self.product.user, 'businessdetails_set', None)
                if business:
                    b = business.first()
                    if b and b.store_promo_enabled and (not b.store_promo_end_date or b.store_promo_end_date > timezone.now()):
                        pct = b.store_promo_percentage
            except Exception:
                pass
        if pct and self.price is not None:
            return round(float(self.price) * (100 - float(pct)) / 100.0, 2)
        return None

    @discounted_price.setter
    def discounted_price(self, val):
        self._discounted_price = val


class ItemImages(models.Model):
    item = models.ForeignKey(UserItems, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(storage=ProductStorage(), upload_to="")
    timestamp = models.DateTimeField(auto_now_add=True)


class UserInvoices(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]
    INVOICE_CHOICES = [
        ('instant', 'Instant'),
        ('installment', 'Installment'),
    ]
    user_id = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='invoice')
    invoice_id = models.CharField(max_length=100, null=False, blank=False)
    invoice_status = models.CharField(max_length=100, null=False, blank=False, choices=STATUS_CHOICES)
    invoice_type = models.CharField(max_length=100, blank=False, null=False, default='instant', choices=INVOICE_CHOICES)
    invoice_payment_type = models.CharField(max_length=100, default=None, blank=True)
    invoice_note = models.TextField(null=True, blank=True)
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=20, null=True, blank=True)
    cashier_id = models.CharField(max_length=100, null=True)
    designated_account_number = models.CharField(max_length=100, null=True, blank=True)
    designated_account_name = models.CharField(max_length=100, null=True, blank=True)
    designated_bank_name = models.CharField(max_length=100, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    # Online Order Fields
    is_online_order = models.BooleanField(default=False)
    delivery_status = models.CharField(max_length=50, default='pending')
    delivery_address = models.TextField(null=True, blank=True)
    delivery_country = models.CharField(max_length=100, null=True, blank=True)
    delivery_state = models.CharField(max_length=100, null=True, blank=True)
    delivery_lga = models.CharField(max_length=100, null=True, blank=True)
    delivery_postal_code = models.CharField(max_length=50, null=True, blank=True)
    delivery_type = models.CharField(max_length=50, default='self')
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)


class FailedWaybills(models.Model):
    invoice = models.ForeignKey(UserInvoices, on_delete=models.CASCADE, related_name='failed_waybills')
    error_message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)


class UserInvoiceItems(models.Model):
    user = models.ForeignKey(UserInvoices, on_delete=models.CASCADE, related_name='invoice_items')
    item_invoice_id = models.CharField(max_length=100, null=False, blank=False)
    item_id = models.CharField(max_length=100, null=False)
    item_name = models.CharField(max_length=100, null=False, blank=False)
    item_amount = models.DecimalField(max_digits=12, decimal_places=2, null=False, blank=False)
    item_buy_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    item_quantity = models.IntegerField(blank=False)
    color_name = models.CharField(max_length=100, null=True, blank=True)
    color_hex = models.CharField(max_length=7, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class SubscriptionInvoices(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='subscription_invoices')
    invoice_id = models.CharField(max_length=100, null=False, blank=False)
    invoice_status = models.CharField(max_length=100, null=False, blank=False, choices=STATUS_CHOICES, default='completed')
    invoice_payment_type = models.CharField(max_length=100, default='wallet', blank=True)
    invoice_note = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=False, blank=False, default=0.00)
    plan_id = models.CharField(max_length=100, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class UserPayroll(models.Model):
    user_id = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='payroll')
    staff_user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='payroll_profile', null=True, blank=True)
    account_number = models.CharField(max_length=100)
    account_id = models.CharField(max_length=100, null=True, blank=False)
    account_name = models.CharField(max_length=100)
    description = models.CharField(max_length=100)
    paystack_recipient_code = models.CharField(max_length=100, null=True, blank=True)
    paystack_reference = models.CharField(max_length=100, null=True, blank=True)

    job_title = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)

    # Encrypted fields
    _pay_amount = models.BinaryField(db_column='pay_amount', null=True)
    _pay_date = models.BinaryField(db_column='pay_date', null=True)
    _pay_frequency = models.BinaryField(db_column='pay_frequency', null=True)
    _allowances = models.BinaryField(db_column='allowances', null=True)
    _deductions = models.BinaryField(db_column='deductions', null=True)

    pay_status = models.CharField(max_length=100, default='active')

    image = models.ImageField(
        upload_to='docs/user/verification/protected/',
        validators=[validate_image],
        null=True,
        blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    # Setters
    def set_pay_amount(self, amount: float):
        self._pay_amount = cipher.encrypt(str(amount))

    def set_pay_date(self, date: str):
        self._pay_date = cipher.encrypt(date)

    def set_pay_frequency(self, freq: str):
        self._pay_frequency = cipher.encrypt(freq)

    def set_allowances(self, amount: float):
        self._allowances = cipher.encrypt(str(amount))

    def set_deductions(self, amount: float):
        self._deductions = cipher.encrypt(str(amount))

    # Getters
    def get_pay_amount(self) -> float:
        val = cipher.decrypt(self._pay_amount) if self._pay_amount else "0.0"
        try:
            return float(val) if val else 0.0
        except ValueError:
            return 0.0

    def get_pay_date(self) -> str:
        return cipher.decrypt(self._pay_date) if self._pay_date else None

    def get_pay_frequency(self) -> str:
        return cipher.decrypt(self._pay_frequency) if self._pay_frequency else None

    def get_allowances(self) -> float:
        val = cipher.decrypt(self._allowances) if self._allowances else "0.0"
        try:
            return float(val) if val else 0.0
        except ValueError:
            return 0.0

    def get_deductions(self) -> float:
        val = cipher.decrypt(self._deductions) if self._deductions else "0.0"
        try:
            return float(val) if val else 0.0
        except ValueError:
            return 0.0

    @property
    def pay_amount(self):
        return self.get_pay_amount()

    @property
    def pay_date(self):
        return self.get_pay_date()

    @property
    def pay_frequency(self):
        return self.get_pay_frequency()

    @property
    def allowances(self):
        return self.get_allowances()

    @property
    def deductions(self):
        return self.get_deductions()



class UserCartItems(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='cart_items')
    item_id = models.CharField(max_length=100)
    item_quantity = models.BigIntegerField(default=1, blank=False)
    color_name = models.CharField(max_length=100, null=True, blank=True)
    color_hex = models.CharField(max_length=7, null=True, blank=True)
    size = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.item_id


class BusinessDetails(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='business_details')
    business_name = models.CharField(max_length=100, null=True, blank=True)
    business_type = models.CharField(max_length=100, null=True, blank=True)
    team_size = models.CharField(max_length=50, null=True, blank=True)
    business_image = models.ImageField(
        upload_to='docs/user/verification/protected/',
        validators=[validate_image],
        null=True,
        blank=True
    )
    enable_ai_calls = models.BooleanField(default=False)
    enable_auto_payroll = models.BooleanField(default=False)
    enable_payroll_otp = models.BooleanField(default=True)
    payroll_overdraft = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    _subscription_expiry = models.BinaryField(null=True, blank=True, db_column='subscription_expiry')
    plan_code = models.BigIntegerField(default=0, null=False, blank=False)
    enable_loyalty = models.BooleanField(default=False)
    vat_percentage = models.FloatField(default=0, blank=False, null=False)
    loyalty_point_equivalent = models.BigIntegerField(default=0)
    
    # Store Setup
    store_setup = models.BooleanField(default=False)
    has_received_setup_email = models.BooleanField(default=False)
    store_countries = models.JSONField(default=list, blank=True, null=True)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    hide_store_name = models.BooleanField(default=False)
    hide_hot_products = models.BooleanField(default=False)
    store_headline = models.CharField(max_length=255, null=True, blank=True)
    store_description = models.TextField(null=True, blank=True)
    store_logo = models.ImageField(storage=BrandStorage(), upload_to="", null=True, blank=True)
    store_banner = models.ImageField(storage=BrandStorage(), upload_to="", null=True, blank=True)
    store_slug = models.CharField(max_length=255, null=True, blank=True)
    store_domain = models.CharField(max_length=255, null=True, blank=True)
    store_custom_domain = models.CharField(max_length=255, null=True, blank=True)
    store_delivery_type = models.CharField(max_length=50, default='self') # self or system
    store_delivery_base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    store_delivery_fee_per_weight = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    store_delivery_pay_on_delivery = models.BooleanField(default=False)
    store_delivery_pay_instantly = models.BooleanField(default=True)
    store_payment_collection = models.CharField(max_length=100, null=True, blank=True)
    store_instant_settlement = models.BooleanField(default=False)
    store_layout_template = models.CharField(max_length=100, default='default')
    store_accent_color = models.CharField(max_length=20, default='#10b981')
    store_theme = models.CharField(max_length=20, default='light') # dark, light, system
    store_category_layout = models.CharField(max_length=50, default='standard') # standard, categorized
    store_operating_hours = models.JSONField(default=default_store_operating_hours, blank=True, null=True)
    is_published = models.BooleanField(default=True)
    store_views = models.BigIntegerField(default=0)
    enable_livechat = models.BooleanField(default=False)
    enable_whatsapp = models.BooleanField(default=False)
    store_whatsapp_number = models.CharField(max_length=50, null=True, blank=True)
    store_social_instagram = models.CharField(max_length=255, null=True, blank=True)
    store_social_twitter = models.CharField(max_length=255, null=True, blank=True)
    store_social_facebook = models.CharField(max_length=255, null=True, blank=True)
    store_shipping_policy_type = models.CharField(max_length=50, default='default')
    store_promo_enabled = models.BooleanField(default=False)
    store_promo_percentage = models.FloatField(default=0.0)
    store_promo_end_date = models.DateTimeField(null=True, blank=True)
    store_custom_shipping_policy = models.TextField(null=True, blank=True)
    store_pickup_state = models.CharField(max_length=100, null=True, blank=True)
    store_pickup_lga = models.CharField(max_length=100, null=True, blank=True)
    store_pickup_address = models.CharField(max_length=255, null=True, blank=True)
    store_pickup_phone = models.CharField(max_length=50, null=True, blank=True)
    store_pickup_email = models.CharField(max_length=255, null=True, blank=True)
    store_pickup_name = models.CharField(max_length=255, null=True, blank=True)
    store_pickup_locations = models.JSONField(default=dict, blank=True, null=True)
    store_authors = models.JSONField(default=list, blank=True, null=True)
    store_featured_author = models.CharField(max_length=255, null=True, blank=True)
    store_featured_author_image = models.TextField(null=True, blank=True)
    developer_mode_enabled = models.BooleanField(default=False)
    store_head_scripts = models.TextField(null=True, blank=True)
    ad_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def set_subscription_expiry(self, dt: datetime):
        self._subscription_expiry = cipher.encrypt(dt.isoformat())

    def get_subscription_expiry(self) -> str:
        if self._subscription_expiry:
            return cipher.decrypt(self._subscription_expiry)
        return None

    @property
    def subscription_expiry(self):
        return self.get_subscription_expiry()

    @subscription_expiry.setter
    def subscription_expiry(self, value: datetime):
        self.set_subscription_expiry(value)

    @property
    def contact_phone(self):
        return self.store_pickup_phone or (self.user.user_phone if hasattr(self, 'user') and self.user else None)

    @property
    def contact_whatsapp(self):
        return self.store_whatsapp_number if self.enable_whatsapp else None

    @property
    def business_address(self):
        return self.store_pickup_address

    @property
    def support_email(self):
        return self.store_pickup_email or (self.user.user_email if hasattr(self, 'user') and self.user else None)




class CashierDepartments(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='departments')
    uniq_id = models.BigAutoField(primary_key=True)
    department_name = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class ProductCategories(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='product_categories')
    uniq_id = models.BigAutoField(primary_key=True)
    category_name = models.CharField(max_length=100, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class FundingInstruments(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    instrument = models.CharField(max_length=100, default=None, blank=False)
    icon = models.CharField(max_length=100, default=None, blank=False)
    description = models.CharField(max_length=100, default=None, blank=False)

    def __str__(self):
        return self.instrument


class CryptoAssets(models.Model):
    crypto_uniq_id = models.BigAutoField(primary_key=True, default=None)
    asset_id = models.CharField(max_length=100, default=None, blank=False, unique=True, error_messages={
        'unique': "Asset already exists"
    })
    name = models.CharField(max_length=100, default=None, blank=False)
    icon = models.ImageField(upload_to=crypto_upload_to, blank=True, null=True)

    def __str__(self):
        return self.name

class CryptoAssetChains(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(CryptoAssets, on_delete=models.CASCADE, related_name='chains')
    chain_id = models.CharField(max_length=100, default=None, blank=False)
    name = models.CharField(max_length=100, default=None, blank=False)
    icon = models.ImageField(upload_to=crypto_upload_to, blank=True, null=True)
    description = models.CharField(max_length=100, default=None, blank=True)

    def __str__(self):
        return self.name

class CryptoLedger(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='crypto_ledger')
    asset = models.CharField(max_length=100, null=False, blank=False)
    asset_chain = models.CharField(max_length=100, null=False, blank=False)
    private_key = models.TextField(null=False, blank=False)
    public_key = models.TextField(null=False, blank=False)
    balance = models.DecimalField(max_digits=20, decimal_places=7, default=0)
    last_checked = models.DateTimeField(auto_now_add=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class CryptoLedgerSweepWallet(models.Model):
    """Model to store target wallets for sweeping crypto balances"""
    uniq_id = models.BigAutoField(primary_key=True)
    asset = models.CharField(max_length=100, null=False, blank=False, help_text="Crypto asset (e.g., USDC, XLM)")
    asset_chain = models.CharField(max_length=100, null=False, blank=False, help_text="Blockchain network (e.g., USDC, XLM)")
    public_key = models.TextField(null=False, blank=False, help_text="Target wallet public key/address for sweeping")
    is_active = models.BooleanField(default=True, help_text="Whether this sweep wallet is active")
    description = models.CharField(max_length=255, blank=True, null=True, help_text="Optional description for this sweep wallet")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['asset', 'asset_chain']]
        verbose_name = "Crypto Sweep Wallet"
        verbose_name_plural = "Crypto Sweep Wallets"
    
    def __str__(self):
        return f"{self.asset} on {self.asset_chain} - {self.public_key[:10]}..."


class FCMDeviceToken(models.Model):
    """Model to store FCM device tokens for push notifications"""
    uniq_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.TextField(null=False, blank=False, help_text="FCM device token")
    device_type = models.CharField(max_length=20, choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')], default='android')
    device_id = models.CharField(max_length=255, blank=True, null=True, help_text="Unique device identifier")
    is_active = models.BooleanField(default=True, help_text="Whether this token is active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['user', 'token']]
        verbose_name = "FCM Device Token"
        verbose_name_plural = "FCM Device Tokens"
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.user_id} - {self.device_type} ({self.token[:20]}...)"


class UserManagers(models.Model):

    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='managers')
    uniq_id = models.BigAutoField(primary_key=True)
    manager_name = models.CharField(max_length=100, null=False, blank=False)
    manager_email = models.CharField(max_length=100, blank=False, null=False)
    manager_password = models.CharField(max_length=100, blank=False, null=False)
    manager_pin = models.CharField(max_length=100, blank=False, null=False)
    manager_department = models.CharField(max_length=100, null=False, blank=False)
    job_title = models.CharField(max_length=100, null=True, blank=True)
    password_changed = models.BooleanField(default=False)
    add_stock = models.BooleanField(default=False)
    edit_stock = models.BooleanField(default=False)
    add_cashier = models.BooleanField(default=False)
    edit_cashier = models.BooleanField(default=False)
    manage_online_store = models.BooleanField(default=False)
    manage_payroll = models.BooleanField(default=False)
    manage_finances = models.BooleanField(default=False)
    image = models.ImageField(
        upload_to='docs/user/verification/protected/',
        validators=[validate_image],
        null=True,
        blank=True
    )

class UserManagerTokens(models.Model):
    user = models.ForeignKey(UserManagers, on_delete=models.CASCADE)
    uniq_id = models.CharField(max_length=100, null=False, blank=False)
    manager_token = models.TextField(blank=False, null=False)
    blacklisted = models.BooleanField(default=False)

class UserWithdrawalAccounts(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    withdrawal_unique = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='withdrawal_accounts')
    account_name = models.CharField(max_length=100, default=None, blank=False)
    bank_name = models.CharField(max_length=100, default=None, blank=False)
    account_number = models.CharField(blank=False, default=None, max_length=100)
    bank_code = models.CharField(max_length=10, default=None, blank=False)
    paystack_recipient_code = models.CharField(max_length=100, null=True, blank=True)
    paystack_reference = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.withdrawal_unique

class BankDepositDetails(models.Model):
    choices = [
        ('owner', 'OWNER'),
        ('staff', 'STAFF')
    ]
    uniq_id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='deposit_details')
    account_owner = models.CharField(max_length=100, null=False, choices=choices, default=None)
    account_reference = models.CharField(default=None, max_length=100)
    collection_id = models.CharField(max_length=100, null=True, default=None)
    bank_name = models.CharField(max_length=100, default=None, blank=False, null=False)
    account_name = models.CharField(max_length=100, blank=False, null=False)
    account_number = models.CharField(max_length=100, default=None, blank=False, null=False)


class Notifications(models.Model):
    not_types = [
        ('auth', 'AUTH'), 
        ('basic', 'BASIC'), 
        ('tranc_success', 'TRANC_SUCCESS'), 
        ('tranc_error', 'TRANC_ERROR')
    ]
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100, default=None)
    description = models.CharField(max_length=100, default=None)
    action_url = models.CharField(max_length=255, null=True, blank=True)
    notification_type = models.CharField(max_length=100, choices=not_types, blank=False, null=False)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)



class SubscriptionPlans(models.Model):

    uniq_id = models.BigAutoField(primary_key=True)
    plan_name = models.CharField(max_length=100)
    inventory = models.BooleanField(default=True)
    collection_accounts = models.CharField(max_length=100, null=False, blank=False)
    ai_manager = models.BooleanField(default=False)
    managers = models.IntegerField(null=False, blank=False, default=1)
    cashiers = models.IntegerField(null=False, blank=False, default=1)
    max_products = models.IntegerField(null=False, blank=False, default=10)
    business_reporting = models.BooleanField(default=False)
    installment_payment = models.BooleanField(default=False)
    online_store = models.BooleanField(default=False)
    payroll = models.CharField(max_length=100, blank=False)
    support = models.BooleanField(default=True)
    description = models.CharField(max_length=100)
    is_popular = models.BooleanField(default=False)
    one_amount = models.CharField(max_length=100, null=False)
    three_months = models.CharField(max_length=100)
    six_months = models.CharField(max_length=100)
    twelve_months = models.CharField(max_length=100)



class DemoRequests(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    full_name = models.CharField(max_length=100, null=True)
    state_city = models.CharField(max_length=100, null=True)
    phone = models.CharField(max_length=100, null=False)
    email = models.CharField(max_length=100, null=False)
    demo_type = models.CharField(max_length=100, null=False)
    timestamp = models.DateTimeField(auto_now_add=True)


class UserAIChat(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='ai_chats')
    session_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    role = models.CharField(max_length=20, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.user.user_id} - {self.role} - {self.timestamp}"


class AllowedCountries(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=5, unique=True)
    currency = models.CharField(max_length=10, default='NGN', null=True, blank=True)
    timezone = models.CharField(max_length=50, default='Africa/Lagos')
    is_active = models.BooleanField(default=True)
    vat_percentage = models.FloatField(default=0.0, blank=True, null=True)
    tier1_daily_limit = models.DecimalField(max_digits=15, decimal_places=2, default=50000.00, null=True, blank=True)
    min_withdrawal_amount = models.DecimalField(max_digits=15, decimal_places=2, default=100.00, null=True, blank=True)
    system_delivery_pod_enabled = models.BooleanField(default=False)
    system_delivery_card_enabled = models.BooleanField(default=True)
    system_arc_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Allowed Countries"

# Livechat Models
class StoreVisitor(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    store = models.ForeignKey(BusinessDetails, on_delete=models.CASCADE, related_name='visitors')
    visitor_name = models.CharField(max_length=255, null=True, blank=True)
    visitor_email = models.EmailField(null=True, blank=True)
    visitor_phone = models.CharField(max_length=30, null=True, blank=True)
    country_code = models.CharField(max_length=10, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    language = models.CharField(max_length=20, null=True, blank=True)
    current_url = models.URLField(max_length=1000, null=True, blank=True)
    is_online = models.BooleanField(default=False)
    is_preview = models.BooleanField(default=False)
    last_active_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

class LiveChat(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
    )
    visitor = models.ForeignKey(StoreVisitor, on_delete=models.CASCADE, related_name='chats')
    store = models.ForeignKey(BusinessDetails, on_delete=models.CASCADE, related_name='livechats')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    notification_sent = models.BooleanField(default=False)
    custom_data = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

class LiveChatMessage(models.Model):
    SENDER_CHOICES = (
        ('visitor', 'Visitor'),
        ('agent', 'Agent'),
    )
    chat = models.ForeignKey(LiveChat, on_delete=models.CASCADE, related_name='messages')
    sender_type = models.CharField(max_length=20, choices=SENDER_CHOICES)
    message_text = models.TextField()
    attachment = models.FileField(storage=LivechatStorage(), upload_to='', null=True, blank=True)
    attachment_type = models.CharField(max_length=50, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


# Online Store Blog Models
class StoreBlogCategory(models.Model):
    business = models.ForeignKey(BusinessDetails, on_delete=models.CASCADE, related_name='blog_categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('business', 'name')
        verbose_name_plural = 'Store Blog Categories'

    def __str__(self):
        return f"{self.name} ({self.business.store_name})"


class StoreBlogPost(models.Model):
    uniq_id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(BusinessDetails, on_delete=models.CASCADE, related_name='blog_posts')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=100, default='General', blank=True)
    summary = models.TextField(blank=True, null=True, help_text="Short excerpt or description")
    content = models.TextField(help_text="Full blog post content / HTML")
    image = models.ImageField(upload_to='store_blog_images/', blank=True, null=True)
    cover_image_url = models.CharField(max_length=500, blank=True, null=True)
    author_name = models.CharField(max_length=150, blank=True, null=True)
    read_time = models.CharField(max_length=50, default='5 min read', blank=True)
    is_published = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('business', 'slug')

    def __str__(self):
        return f"{self.title} - {self.business.store_name}"

    def get_image_url(self):
        if self.image:
            try:
                return self.image.url
            except Exception:
                pass
        if self.cover_image_url:
            return self.cover_image_url
        return '/static/assets/image/blog/hero_desert_dunes.jpg'


class StaffPosLogins(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='pos_logins')
    staff = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='staff_pos_logins')
    terminal_id = models.CharField(max_length=100)
    login_time = models.DateTimeField(auto_now_add=True)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=20, default='online') # online, closed


class ProductReview(models.Model):
    item = models.ForeignKey(UserItems, on_delete=models.CASCADE, related_name='reviews')
    reviewer_name = models.CharField(max_length=100)
    reviewer_email = models.EmailField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)  # 1-5
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    is_verified_buyer = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reviewer_name} - {self.rating}★ on {self.item.item_name}"

class ReviewToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(UserItems, on_delete=models.CASCADE, related_name='review_tokens')
    invoice = models.ForeignKey(UserInvoices, on_delete=models.CASCADE, related_name='review_tokens')
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    customer_email = models.EmailField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Token for {self.item.item_name} ({'Used' if self.is_used else 'Unused'})"

class JobPosition(models.Model):
    JOB_TYPES = (
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
    )
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    location = models.CharField(max_length=100, default="Remote")
    job_type = models.CharField(max_length=50, choices=JOB_TYPES, default='full_time')
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while JobPosition.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class JobApplication(models.Model):
    job = models.ForeignKey(JobPosition, on_delete=models.CASCADE, related_name='applications')
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    resume_link = models.URLField(max_length=500)
    cover_letter = models.TextField(blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.full_name} - {self.job.title}"


class TeamMember(models.Model):
    DEPARTMENT_CHOICES = (
        ('leadership', 'Leadership'),
        ('engineering', 'Engineering'),
        ('product', 'Product'),
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
    )
    
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES, default='leadership')
    image = models.ImageField(upload_to='team/', blank=True, null=True)
    order = models.IntegerField(default=0, help_text="Sort order (lower numbers appear first)")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'name']
        
    def __str__(self):
        return self.name


class SiteSettings(models.Model):
    """Singleton model for site-wide settings like contact info, social links, etc."""
    email = models.EmailField(default='help@flezpay.com')
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(default='Lagos, Nigeria')
    working_hours = models.CharField(max_length=100, default='Mon - Fri: 9:00AM - 6:00PM')
    map_embed_url = models.TextField(blank=True, default='https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d253682.46313480816!2d3.1438713!3d6.5480357!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x103b8b2ae68280c1%3A0xdc9e87a367c3d9cb!2sLagos%2C%20Nigeria!5e0!3m2!1sen!2sng!4v1700000000000!5m2!1sen!2sng')
    map_directions_url = models.URLField(blank=True, default='https://maps.google.com/?q=Lagos,Nigeria')
    twitter_url = models.URLField(blank=True, default='')
    linkedin_url = models.URLField(blank=True, default='')
    instagram_url = models.URLField(blank=True, default='')
    facebook_url = models.URLField(blank=True, default='')
    
    # Promo Banner settings
    promo_banner_enabled = models.BooleanField(default=True)
    promo_plan = models.ForeignKey('SubscriptionPlans', null=True, blank=True, on_delete=models.SET_NULL, related_name='promo_settings')
    promo_duration = models.CharField(max_length=50, default='one_amount')
    
    # Image & Video Generation settings
    user_image_generation_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.05, help_text="Amount in USD to charge users for generating an AI image")
    ai_generation_model = models.CharField(max_length=50, default='gemini-3-pro-image', choices=[
        ('gemini-3-pro-image', 'Gemini 3 Pro Image'),
        ('gemini-2.5-flash-image', 'Gemini 2.5 Flash Image')
    ], help_text="The AI model used for image generation")
    user_video_generation_cost_usd = models.DecimalField(max_digits=10, decimal_places=2, default=0.20, help_text="Amount in USD to charge users for generating an AI video")
    ai_video_generation_model = models.CharField(max_length=50, default='veo-3.1-generate-preview', choices=[
        ('veo-3.1-generate-preview', 'Veo 3.1 Generate'),
        ('veo-3.1-fast-generate-preview', 'Veo 3.1 Fast Generate'),
        ('veo-3.1-lite-generate-preview', 'Veo 3.1 Lite Generate'),
    ], help_text="The AI model used for video generation")

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return 'Site Settings'

    def save(self, *args, **kwargs):
        # Enforce singleton: always use pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class ContactMessage(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('ongoing', 'Ongoing'),
        ('resolved', 'Resolved'),
    )
    
    name = models.CharField(max_length=150)
    position = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} - {self.email}"


class CloudflareDNSRecord(models.Model):
    """
    Tracks DNS records created/managed on Cloudflare.
    Provides an audit trail and enables fast lookup for cleanup operations.
    """
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='dns_records')
    subdomain = models.CharField(max_length=255, unique=True, db_index=True,
                                 help_text='Subdomain part only (e.g. "shop")')
    full_domain = models.CharField(max_length=255, db_index=True,
                                   help_text='Full domain (e.g. "shop.maxyfleets.com")')
    record_type = models.CharField(max_length=10, default='A',
                                   help_text='DNS record type (A, CNAME, etc.)')
    record_id = models.CharField(max_length=100,
                                 help_text='Cloudflare DNS record ID')
    zone_id = models.CharField(max_length=100,
                               help_text='Cloudflare zone ID')
    target_value = models.CharField(max_length=255,
                                    help_text='Record value (IP for A, hostname for CNAME)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cloudflare DNS Record'
        verbose_name_plural = 'Cloudflare DNS Records'

    def __str__(self):
        return f'{self.full_domain} -> {self.target_value} ({self.record_type})'


class Backer(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    logo = models.ImageField(upload_to=user_upload_to, null=True, blank=True)
    url = models.URLField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return self.name or "Unnamed Backer"


class POSKitOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
    ]
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='pos_orders')
    units = models.IntegerField(default=1)
    email = models.CharField(max_length=100)
    phone = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"POS Order {self.id} for {self.email}"

class GrowthPromotion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='promotions')
    title = models.CharField(max_length=200, default="New Promotion")
    message = models.TextField(blank=True, null=True)
    promote_type = models.CharField(max_length=50) # product, group, store, discount, new
    action_type = models.CharField(max_length=50) # buy, visit, message, call, learn
    budget_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    duration_days = models.IntegerField(default=7)
    audience_type = models.CharField(max_length=50, default='near') # near, past, similar, custom
    status = models.CharField(max_length=50, default='draft') # active, completed, draft, reviewing, paused
    
    # Custom audience settings
    custom_locations = models.TextField(blank=True, null=True)
    custom_age_min = models.IntegerField(blank=True, null=True)
    custom_age_max = models.IntegerField(blank=True, null=True)
    custom_interests = models.TextField(blank=True, null=True)
    
    # Selected product
    product = models.ForeignKey(UserItems, on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions')
    
    # Campaign cover image (uploaded or AI-generated URL)
    cover_image = models.TextField(blank=True, null=True)  # stores URL or base64 data URI
    
    # Performance Metrics
    amount_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sales_generated = models.IntegerField(default=0)
    customers_gained = models.IntegerField(default=0)
    profit_impact = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    views = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    
    # Facebook API IDs
    fb_campaign_id = models.CharField(max_length=100, blank=True, null=True)
    fb_adset_id = models.CharField(max_length=100, blank=True, null=True)
    fb_ad_id = models.CharField(max_length=100, blank=True, null=True)

    # Financial Origin & Tracking
    amount_debited = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    is_external = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

class SystemErrorLog(models.Model):
    LOG_TYPES = (
        ('withdrawal', 'Withdrawal Error'),
        ('waybill', 'Waybill Error'),
        ('gemini', 'Gemini Image Generation Error'),
    )
    log_type = models.CharField(max_length=50, choices=LOG_TYPES)
    message = models.TextField()
    traceback = models.TextField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    user = models.ForeignKey(UserSecure, on_delete=models.SET_NULL, null=True, blank=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)


class PremiumStoreLayout(models.Model):
    LAYOUT_CHOICES = (
        ('luxe-horizon', 'Horizon Luxe'),
        ('vanguard-atelier', 'Atelier Vanguard'),
        ('metro-pulse', 'Metro Pulse'),
        ('folio-press', 'Folio Press'),
        ('premium-commerce-editorial', 'Premium Commerce Editorial'),
    )
    layout_id = models.CharField(max_length=50, unique=True, choices=LAYOUT_CHOICES)
    name = models.CharField(max_length=100)
    price_ngn = models.DecimalField(max_digits=12, decimal_places=2, default=20000.00, help_text="Price in Nigerian Naira (NGN)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Premium Store Layout'
        verbose_name_plural = 'Premium Store Layouts'

    def __str__(self):
        return f"{self.name} ({self.layout_id}) - ₦{self.price_ngn:,.2f}"


class StoreLayoutPurchase(models.Model):
    user = models.ForeignKey(UserSecure, on_delete=models.CASCADE, related_name='layout_purchases')
    business = models.ForeignKey('BusinessDetails', on_delete=models.CASCADE, related_name='layout_purchases', null=True, blank=True)
    layout_id = models.CharField(max_length=50, db_index=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, help_text="Amount charged in user's currency")
    currency = models.CharField(max_length=10, default='NGN', help_text="Currency used for purchase")
    amount_in_ngn = models.DecimalField(max_digits=12, decimal_places=2, help_text="Configured price in NGN at purchase time")
    exchange_rate = models.DecimalField(max_digits=14, decimal_places=6, default=1.0, help_text="Exchange rate (NGN to user currency)")
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'layout_id')
        verbose_name = 'Store Layout Purchase'
        verbose_name_plural = 'Store Layout Purchases'

    def __str__(self):
        return f"{self.user.user_email} unlocked {self.layout_id} ({self.currency} {self.amount_paid})"


class StoreLayoutCustomization(models.Model):
    business = models.ForeignKey('BusinessDetails', on_delete=models.CASCADE, related_name='layout_customizations')
    layout_id = models.CharField(max_length=50, db_index=True)
    sections_config = models.JSONField(default=list, blank=True)
    custom_elements = models.JSONField(default=list, blank=True)
    general_settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('business', 'layout_id')
        verbose_name = 'Store Layout Customization'
        verbose_name_plural = 'Store Layout Customizations'

    def __str__(self):
        return f"{self.business_id} - {self.layout_id} Customization"



def user_has_purchased_layout(user, layout_id):
    """Check if user owns a specific store layout."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    # If not a premium layout, it's free / always available
    if layout_id not in ('luxe-horizon', 'vanguard-atelier'):
        return True
    return StoreLayoutPurchase.objects.filter(user=user, layout_id=layout_id).exists()


def user_has_any_premium_layout(user):
    """Check if user has purchased at least one premium layout."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return StoreLayoutPurchase.objects.filter(user=user).exists()


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    members = models.ManyToManyField('UserSecure', related_name='admin_departments', blank=True, limit_choices_to={'is_superuser': True})
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Ticket(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('mid', 'Mid'),
        ('high', 'High'),
    ]
    ticket_number = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='mid', db_index=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    assigned_admin = models.ForeignKey(UserSecure, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets', limit_choices_to={'is_staff': True})
    affected_users = models.ManyToManyField(UserSecure, related_name='support_tickets', blank=True)
    created_by = models.ForeignKey(UserSecure, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_tickets')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return f"{self.ticket_number} - {self.subject}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            # Generate a unique ticket number
            last_ticket = Ticket.objects.all().order_by('id').last()
            if not last_ticket:
                new_number = 'TKT-000001'
            else:
                last_id = int(last_ticket.ticket_number.split('-')[1])
                new_number = f'TKT-{(last_id + 1):06d}'
            self.ticket_number = new_number
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super(Ticket, self).save(*args, **kwargs)

class TicketMessage(models.Model):
    MESSAGE_TYPES = [
        ('public_reply', 'Public Reply'),
        ('internal_note', 'Internal Note'),
        ('system', 'System'),
    ]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender_admin = models.ForeignKey(UserSecure, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_admin_messages')
    sender_user = models.ForeignKey(UserSecure, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_user_messages')
    message = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='public_reply')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        sender = self.sender_admin or self.sender_user or 'System'
        return f"Message by {sender} on {self.ticket.ticket_number}"

