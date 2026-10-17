import re
from django.utils.translation import gettext_lazy as _

from django.utils.timezone import localtime

from django.db.models import Count, Sum
from rest_framework import serializers
from django.conf import settings
from urllib.parse import urljoin
from api import models
from api.functions import misc
from api.models import UserManagers


class UserTransactionsSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return localtime(obj.timestamp).isoformat()

    class Meta:
        model = models.UserTransactions
        fields = '__all__'
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        user_id = instance.destination_id
        
        # Only attempt lookup if the ID is numeric (internal user ID)
        if user_id and str(user_id).isdigit():
            user_details = models.UserDetails.objects.filter(user_id=user_id).first()
            if user_details:
                request = self.context.get('request')
                host_url = request.build_absolute_uri('/') if request else settings.DEFAULT_HOST_URL
                user_avatar_url = urljoin(host_url, f"{settings.MEDIA_URL}{user_details.user_avatar}")
                data['source'] = {
                    'name': f"{user_details.first_name} {user_details.last_name}",
                    'image': user_avatar_url
                }
        return data


class UserManagersSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserManagers
        fields = "__all__"
        extra_kwargs = {
            'user': {'write_only': True},
            'manager_pin': {'write_only': True},
            'manager_password': {'write_only': True}
        }

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def validate(self, data):
        manager_email = data.get("manager_email")
        if manager_email:
            # Check UserManagers
            qs = UserManagers.objects.filter(manager_email__iexact=manager_email)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    "manager_email": str(_("A manager with this email already exists."))
                })
            
            # Check UserSecure (main user table)
            from api.models import UserSecure
            user_secure = UserSecure.objects.filter(user_email__iexact=manager_email).first()
            if user_secure:
                if not self.instance:
                    raise serializers.ValidationError({
                        "manager_email": str(_("This email is already associated with another account."))
                    })
                elif self.instance.manager_email.lower() != manager_email.lower():
                    raise serializers.ValidationError({
                        "manager_email": str(_("This email is already associated with another account."))
                    })
        return data

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.image:
            request = self.context.get('request')
            host_url = request.build_absolute_uri('/') if request else settings.DEFAULT_HOST_URL
            rep['image'] = urljoin(host_url, f"{instance.image.url}")
        return rep

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserDetails
        fields = ['user_country', 'first_name', 'last_name', 'user_avatar']

    def to_representation(self, instance):
        user = super().to_representation(instance)
        user_id = instance.user_id
        user_details = models.UserDetails.objects.filter(user_id=user_id).first()
        if user_details:
            try:
                user_avatar_url = user_details.user_avatar.url if user_details.user_avatar else None
            except Exception:
                user_avatar_url = None
            user = {
                'first_name': user_details.first_name,
                'last_name': user_details.last_name,
                'user_country': user_details.user_country,
                'user_avatar': user_avatar_url
            }
        return user

class NotificationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Notifications
        fields = '__all__'

class DemoRequestsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DemoRequests
        fields = '__all__'
        extra_kwargs = {
            'uniq_id': {'read_only': True}
        }


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SubscriptionPlans
        fields = '__all__'
    

class BankDepositDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BankDepositDetails
        fields = '__all__'
        extra_kwargs = {
            'user': {"write_only": True}
        }

class SupportSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserSupport
        fields = ['support_phone', 'support_description', 'support_email']


class FaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AskedQuestions
        fields = '__all__'



class SubscriptionInvoicesSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return localtime(obj.timestamp).isoformat()

    class Meta:
        model = models.SubscriptionInvoices
        fields = "__all__"
        extra_kwargs = {
            'user': {"write_only": True}
        }

class UserInvoicesSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return localtime(obj.timestamp).isoformat()

    class Meta:
        model = models.UserInvoices
        fields = "__all__"
        extra_kwargs = {
            'user_id': {"write_only": True}
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        invoice_items = models.UserInvoiceItems.objects.filter(item_invoice_id=instance.invoice_id)
        data['invoice_items'] = UserInvoiceItemsSerializer(invoice_items, many=True).data
        data['total_amount'] = sum(item.item_amount * item.item_quantity for item in invoice_items)
        
        # Calculate total paid from transactions linked to this invoice's virtual account
        if instance.designated_account_number:
            total_paid = models.UserTransactions.objects.filter(
                user=instance.user_id,
                trx_type='credit',
                trx_status='completed',
                user_collection_id=instance.designated_account_number
            ).aggregate(total=Sum('trx_amount'))['total'] or 0.0
            data['total_paid'] = float(total_paid)
        else:
            # For instant invoices, if completed, total_paid = total_amount
            data['total_paid'] = float(data['total_amount']) if instance.invoice_status == 'completed' else 0.0
            
        return data


class UserInvoiceItemsSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return localtime(obj.timestamp).isoformat()
        
    def get_image_url(self, obj):
        try:
            item = models.UserItems.objects.get(item_id=obj.item_id)
            first_image = item.images.first()
            if first_image and first_image.image:
                return first_image.image.url
        except Exception:
            pass
        return None

    class Meta:
        model = models.UserInvoiceItems
        fields = '__all__'
        extra_kwargs = {
            'user': {"write_only": True}
        }

    def validate(self, data):
        item_id = data['item_id']
        if not models.UserItems.objects.filter(item_id=item_id).exists():
            raise Exception("Item ID is not valid")
        return data

class UserPayrollSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return localtime(obj.timestamp).isoformat()

    pay_amount = serializers.SerializerMethodField()
    pay_date = serializers.SerializerMethodField()
    pay_frequency = serializers.SerializerMethodField()
    allowances = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField()
    last_payment_date = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True)
    pos_access = serializers.SerializerMethodField()
    can_apply_discounts = serializers.SerializerMethodField()
    can_process_refunds = serializers.SerializerMethodField()
    can_view_reports = serializers.SerializerMethodField()

    class Meta:
        model = models.UserPayroll
        exclude = ['_pay_amount', '_pay_date', '_pay_frequency', '_allowances', '_deductions', 'user_id']

    def get_pay_amount(self, obj):
        return obj.get_pay_amount()

    def get_pay_date(self, obj):
        return obj.get_pay_date()

    def get_pay_frequency(self, obj):
        return obj.get_pay_frequency()

    def get_allowances(self, obj):
        return obj.get_allowances()

    def get_deductions(self, obj):
        return obj.get_deductions()
        
    def get_pos_access(self, obj):
        if obj.staff_user and obj.staff_user.details.exists():
            return obj.staff_user.details.first().pos_access
        return False

    def get_can_apply_discounts(self, obj):
        if obj.staff_user and obj.staff_user.details.exists():
            return obj.staff_user.details.first().can_apply_discounts
        return False

    def get_can_process_refunds(self, obj):
        if obj.staff_user and obj.staff_user.details.exists():
            return obj.staff_user.details.first().can_process_refunds
        return False

    def get_can_view_reports(self, obj):
        if obj.staff_user and obj.staff_user.details.exists():
            return obj.staff_user.details.first().can_view_reports
        return False
        
    def get_last_payment_date(self, obj):
        last_trx = models.UserTransactions.objects.filter(
            user=obj.user_id,
            trx_source='Payroll',
            user_collection_id=obj.account_number,
            trx_type='payment',
            trx_status__in=['completed', 'pending']
        ).order_by('-timestamp').first()
        if last_trx:
            return localtime(last_trx.timestamp).strftime("%b %d, %Y")
        return None

    def update(self, instance, validated_data):
        if 'pay_amount' in self.initial_data:
            instance.set_pay_amount(self.initial_data.get('pay_amount'))

        if 'pay_date' in self.initial_data:
            instance.set_pay_date(self.initial_data.get('pay_date'))

        if 'pay_frequency' in self.initial_data:
            instance.set_pay_frequency(self.initial_data.get('pay_frequency'))

        if 'allowances' in self.initial_data:
            instance.set_allowances(self.initial_data.get('allowances'))

        if 'deductions' in self.initial_data:
            instance.set_deductions(self.initial_data.get('deductions'))

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def create(self, validated_data):
        request = self.context.get('request')
        user_id = misc.get_id(request)
        user_instance = models.UserSecure.objects.get(user_id=user_id)

        # Encrypted fields
        pay_amount = self.initial_data.get('pay_amount')
        pay_date = self.initial_data.get('pay_date')
        pay_frequency = self.initial_data.get('pay_frequency')
        allowances = self.initial_data.get('allowances')
        deductions = self.initial_data.get('deductions')
        image = request.FILES.get('image')

        instance = models.UserPayroll(
            user_id=user_instance,
            account_number=validated_data.get('account_number'),
            account_id=validated_data.get('account_id'),
            account_name=validated_data.get('account_name'),
            description=validated_data.get('description'),
            job_title=validated_data.get('job_title'),
            department=validated_data.get('department'),
            bank_name=validated_data.get('bank_name'),
            pay_status=validated_data.get('pay_status', 'active'),
            paystack_recipient_code=validated_data.get('paystack_recipient_code'),
            paystack_reference=validated_data.get('paystack_reference'),
        )

        if pay_amount:
            instance.set_pay_amount(pay_amount)
        if pay_date:
            instance.set_pay_date(pay_date)
        if pay_frequency:
            instance.set_pay_frequency(pay_frequency)
        if allowances:
            instance.set_allowances(allowances)
        if deductions:
            instance.set_deductions(deductions)
        if image:
            instance.image = image

        instance.save()
        return instance

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        account_number = attrs.get('account_number')
        account_id = attrs.get('account_id')
        if account_number and account_id:
            payroll_exists = models.UserPayroll.objects.filter(
                account_number=account_number,
                account_id=account_id
            )
            if instance:
                payroll_exists = payroll_exists.exclude(pk=instance.pk)

            if payroll_exists.exists():
                raise serializers.ValidationError("Account details already exist")
        return attrs

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.image:
            request = self.context.get('request')
            host_url = request.build_absolute_uri('/') if request else settings.DEFAULT_HOST_URL
            rep['image'] = urljoin(host_url, f"{instance.image.url}")
        return rep





class StaffSecureSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user_email', read_only=True)
    account_name = serializers.SerializerMethodField()
    job_title = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    account_number = serializers.SerializerMethodField()
    pay_status = serializers.SerializerMethodField()
    pos_access = serializers.SerializerMethodField()
    can_apply_discounts = serializers.SerializerMethodField()
    can_process_refunds = serializers.SerializerMethodField()
    can_view_reports = serializers.SerializerMethodField()
    id = serializers.IntegerField(source='uniq_id')
    image = serializers.SerializerMethodField()
    bank_name = serializers.SerializerMethodField()
    account_id = serializers.SerializerMethodField()
    paystack_recipient_code = serializers.SerializerMethodField()
    paystack_reference = serializers.SerializerMethodField()
    pay_amount = serializers.SerializerMethodField()
    pay_date = serializers.SerializerMethodField()
    pay_frequency = serializers.SerializerMethodField()
    allowances = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField()
    last_payment_date = serializers.SerializerMethodField()

    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()
    
    class Meta:
        model = models.UserSecure
        fields = [
            'id', 'user_id', 'email', 'user_email', 'account_name', 'first_name', 'last_name', 'job_title', 'department', 
            'account_number', 'pay_status', 'pos_access', 'can_apply_discounts',
            'can_process_refunds', 'can_view_reports', 'image', 'bank_name', 'account_id',
            'paystack_recipient_code', 'paystack_reference', 'pay_amount', 'pay_date',
            'pay_frequency', 'allowances', 'deductions', 'last_payment_date', 'is_active', 'phone_number', 'timestamp'
        ]

    def get_first_name(self, obj):
        details = obj.details.first()
        return details.first_name if details else ""
        
    def get_last_name(self, obj):
        details = obj.details.first()
        return details.last_name if details else ""

    def get_phone_number(self, obj):
        return str(obj.user_phone) if obj.user_phone else ""
        
    def get_timestamp(self, obj):
        return obj.date_created * 1000 if obj.date_created else None


    def get_account_name(self, obj):
        details = obj.details.first()
        return f"{details.first_name} {details.last_name}" if details else "Unknown"

    def get_job_title(self, obj):
        details = obj.details.first()
        return details.job_title if details else ""

    def get_department(self, obj):
        details = obj.details.first()
        return details.department if details else ""

    def get_account_number(self, obj):
        from api.models import BankDepositDetails
        if obj.business_owner:
            deposit = BankDepositDetails.objects.filter(
                user=obj.business_owner,
                account_owner='staff',
                account_reference=str(obj.uniq_id)
            ).first()
            if deposit and deposit.account_number:
                return deposit.account_number
                
        payroll = obj.payroll_profile.first()
        return payroll.account_number if payroll else ""

    def get_pay_status(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.pay_status if payroll else "inactive"
        
    def get_pos_access(self, obj):
        details = obj.details.first()
        return details.pos_access if details else False

    def get_can_apply_discounts(self, obj):
        details = obj.details.first()
        return details.can_apply_discounts if details else False

    def get_can_process_refunds(self, obj):
        details = obj.details.first()
        return details.can_process_refunds if details else False

    def get_can_view_reports(self, obj):
        details = obj.details.first()
        return details.can_view_reports if details else False
        
    def get_image(self, obj):
        details = obj.details.first()
        if details and details.user_avatar:
            try:
                url = details.user_avatar.url
                if url and 'placeholder_avi' not in url:
                    return url
            except Exception:
                pass
        payroll = obj.payroll_profile.first()
        if payroll and payroll.image:
            try:
                url = payroll.image.url
                if url and 'placeholder_avi' not in url:
                    return url
            except Exception:
                pass
        return None
        
    def get_bank_name(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.bank_name if payroll else ""
        
    def get_account_id(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.account_id if payroll else ""
        
    def get_paystack_recipient_code(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.paystack_recipient_code if payroll else ""
        
    def get_paystack_reference(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.paystack_reference if payroll else ""
        
    def get_pay_amount(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.get_pay_amount() if payroll else 0.0
        
    def get_pay_date(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.get_pay_date() if payroll else ""
        
    def get_pay_frequency(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.get_pay_frequency() if payroll else ""
        
    def get_allowances(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.get_allowances() if payroll else {}
        
    def get_deductions(self, obj):
        payroll = obj.payroll_profile.first()
        return payroll.get_deductions() if payroll else {}
        
    def get_last_payment_date(self, obj):
        last_trx = models.UserTransactions.objects.filter(
            user=obj.business_owner,
            trx_source='Payroll',
            user_collection_id=self.get_account_number(obj),
            trx_type='payment',
            trx_status__in=['completed', 'pending']
        ).order_by('-timestamp').first()
        if last_trx:
            return localtime(last_trx.timestamp).strftime("%b %d, %Y")
        return None



class ItemImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ItemImages
        fields = ['id', 'image', 'timestamp']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if instance.image:
            rep['image'] = instance.image.url
        return rep


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProductVariant
        fields = '__all__'


class UserItemsSerializer(serializers.ModelSerializer):
    images = ItemImagesSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    total_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = models.UserItems
        fields = ['id', 'item_name', 'item_amount', 'item_description', 'item_id',
                  'item_serial_number', 'item_quantity', 'item_expiry', 'item_weight', 'item_weight_unit',
                  'item_buy_amount', 'last_adjusted_date', 'item_category', 'item_department', 'item_colors', 'color_name', 'color_hex', 'images', 'variants', 'total_stock', 'in_store', 'is_featured', 'is_promo', 'promo_amount',
                  'is_digital', 'digital_file', 'digital_file_name', 'digital_file_size', 'digital_format',
                  'book_author', 'book_publisher', 'book_publication_date', 'book_isbn', 'book_pages',
                  'book_language', 'book_edition', 'book_reading_time', 'book_sample_file', 'book_sample_text', 'book_series']

    def get_total_stock(self, obj):
        variants = obj.variants.all()
        if variants.exists():
            return sum(v.quantity for v in variants)
        return obj.item_quantity

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('item_serial_number'):
            data['item_serial_number'] = re.sub(r'\s+', '', data['item_serial_number'])
        if hasattr(instance, 'promo_amount'):
            data['promo_percentage'] = instance.promo_amount
        if instance.digital_file:
            try:
                data['digital_file_url'] = instance.digital_file.url
            except Exception:
                data['digital_file_url'] = None
        if instance.book_sample_file:
            try:
                data['book_sample_file_url'] = instance.book_sample_file.url
            except Exception:
                data['book_sample_file_url'] = None
        return data


class UserCartItemsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.UserCartItems
        fields = '__all__'
        extra_kwargs = {
            'user': {"write_only": True}
        }

    def validate(self, data):
        item_id = data['item_id']
        if not models.UserItems.objects.filter(item_id=item_id).exists():
            raise Exception("Item ID is not valid")
        return data

    def create(self, validated_data):
        item_id = validated_data['item_id']
        user_id = validated_data['user']
        existing_item = models.UserCartItems.objects.filter(item_id=item_id, user_id=user_id).first()
        if existing_item:
            existing_item.item_quantity = validated_data.get('item_quantity')  # Update the quantity if needed
            existing_item.save()
            return existing_item
        else:
            return super().create(validated_data)

    def update(self, instance, validated_data):
        item_id = validated_data.get('item_id', instance.item_id)
        if instance.item_id != item_id:
            raise serializers.ValidationError("Cannot update item_id, only quantity or other fields.")

        instance.item_quantity = validated_data.get('item_quantity', instance.quantity)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        item_id = instance.item_id
        item_details = models.UserItems.objects.filter(item_id=item_id).first()
        if item_details:
            data['item_details'] = {
                'item_name': item_details.item_name,
                'item_amount': item_details.item_amount,
                'description': item_details.item_description
            }
        return data


class UserVerificationSerializer(serializers.ModelSerializer):
    driver_licence = serializers.FileField(required=False, allow_null=True)
    proof_of_address = serializers.FileField(required=False, allow_null=True)
    user_image = serializers.FileField(required=False, allow_null=True)
    user_video = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = models.UserVerificationDetails
        fields = '__all__'
        extra_kwargs = {
            'user': {"write_only": True,}
        }


class FundingInstrumentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FundingInstruments
        fields = '__all__'


class DepartmentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CashierDepartments
        fields = '__all__'
        extra_kwargs = {
            'user': {'write_only': True}
        }

class ProductCategoriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProductCategories
        fields = '__all__'
        extra_kwargs = {
            'user': {'write_only': True}
        }

class CryptoAssetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CryptoAssets
        fields = ['name', 'icon', 'asset_id']
        extra_kwargs = {
            'crypto_uniq_id': {"write_only": True}
        }

    def to_representation(self, instance):
        asset = super().to_representation(instance)
        chains = []
        if instance.chains:
            for chain in instance.chains.all():
                try:
                    icon_url = chain.icon.url if chain.icon else None
                except Exception:
                    icon_url = None
                chains.append({
                    'id': chain.chain_id,
                    'name': chain.name,
                    'icon': icon_url,
                    'description': chain.description
                })
        asset['chains'] = chains

        if instance.icon:
            try:
                asset['icon'] = instance.icon.url
            except Exception:
                asset['icon'] = None
        return asset


class CryptoAssetChainsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CryptoAssetChains
        fields = '__all__'

    def validate(self, data):
        instance = models.CryptoAssetChains.objects.filter(asset_id=data.get('asset'), chain_id=data.get('chain_id'))
        if instance.exists():
            raise serializers.ValidationError('Chain already exists')
        return data

class UserWithdrawalAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserWithdrawalAccounts
        fields = ['withdrawal_unique', 'account_name', 'account_number',
                  'bank_code', 'bank_name', 'uniq_id', 'paystack_recipient_code',
                  'paystack_reference'
                  ]
        extra_kwargs = {
            'withdrawal_unique': {"write_only": True}
        }
    def validate(self, data):
        accounts = models.UserWithdrawalAccounts.objects.filter(withdrawal_unique=data['withdrawal_unique'], bank_code=data['bank_code'], account_number=data['account_number'])
        if accounts.exists():
            raise Exception('bank account already exists')
        return data

class UserBusinessDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.BusinessDetails
        exclude = ['_subscription_expiry']
        extra_kwargs = {
            'user': {"write_only": True}
        }

    def create(self, validated_data):
        expiry = validated_data.pop("subscription_expiry", None)
        instance, _ = models.BusinessDetails.objects.update_or_create(
            user=validated_data.get("user"),
            defaults=validated_data
        )
        if expiry:
            instance.set_subscription_expiry(expiry)
            instance.save()
        return instance

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        if instance.business_image and hasattr(instance.business_image, "url"):
            host_url = request.build_absolute_uri('/') if request else settings.DEFAULT_HOST_URL
            avatar_url = urljoin(host_url, f"{instance.business_image.url}")
            rep["business_image"] = avatar_url
        else:
            rep["business_image"] = None

        if instance.store_logo and hasattr(instance.store_logo, "url"):
            host_url = request.build_absolute_uri('/') if request else settings.DEFAULT_HOST_URL
            logo_url = urljoin(host_url, f"{instance.store_logo.url}")
            rep["store_logo"] = logo_url
        else:
            rep["store_logo"] = None
        expiry = instance.get_subscription_expiry()
        if expiry:
            rep['subscription_expiry'] = expiry
        else:
            # return default ISO datetime string or empty string
            rep['subscription_expiry'] = "0000-00-00T00:00:00Z"
            
        from django.db.models import Q
        rep['online_orders_pending_count'] = models.UserInvoices.objects.filter(
            Q(delivery_status='pending') | Q(delivery_status='processing'),
            user_id=instance.user, 
            is_online_order=True, 
            invoice_status='completed'
        ).count()
        return rep

class UserSecureSerializer(serializers.ModelSerializer):

    details = UserDetailSerializer(many=True, read_only=True)
    items = UserItemsSerializer(many=True, read_only=True)
    verification = UserVerificationSerializer(many=True, read_only=True)
    cart_items = UserCartItemsSerializer(many=True, read_only=True)
    withdrawal_accounts = UserWithdrawalAccountSerializer(many=True, read_only=True)
    deposit_details = serializers.SerializerMethodField()
    deposit_account = serializers.SerializerMethodField()
    notifications = NotificationsSerializer(many=True, read_only=True)
    payroll = UserPayrollSerializer(many=True, read_only=True)
    invoice = serializers.SerializerMethodField()
    business_details = UserBusinessDetailsSerializer(many=True, read_only=True)
    departments = DepartmentsSerializer(many=True, read_only=True)
    product_categories = ProductCategoriesSerializer(many=True, read_only=True)
    managers = UserManagersSerializer(many=True, read_only=True)

    # Computed fields
    most_frequent_transactions = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()

    def get_invoice(self, obj):
        return UserInvoicesSerializer(obj.invoice.all().order_by('-timestamp'), many=True).data

    class Meta:
        model = models.UserSecure
        fields = ['user_phone', 'user_id', 'account_type', 'user_type', 'is_staff', 'is_superuser', 'user_email', 'date_created',
                  'is_verified', 'kyc_verified', 'kyb_verified', 'transfers_disabled', 'withdrawals_disabled', 'details', 'verification', 'cart_items',
                  'items', 'withdrawal_accounts', 'deposit_details', 'deposit_account', 'notifications',
                  'most_frequent_transactions', 'payroll', 'invoice', 'business_details', 'departments', 'product_categories', 'managers', 'transactions']
        extra_kwargs = {
            'user_pass': {"write_only": True}
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['notifications'] = sorted(data['notifications'], key=lambda x: x['id'], reverse=True)
        return data

    def get_most_frequent_transactions(self, obj):
        most_frequent_collections = (
            models.UserTransactions.objects.filter(user=obj, trx_type="transfer")
            .values('user_collection_id')
            .annotate(count=Count('user_collection_id'))
            .order_by('-count')
        )

        transactions = []
        for collection in most_frequent_collections:
            trx = models.UserTransactions.objects.filter(
                user_collection_id=collection['user_collection_id'], user=obj
            ).order_by('-timestamp').first()  # Get the latest transaction for each collection_id

            if trx:
                transactions.append(trx)

        return UserTransactionsSerializer(transactions, many=True).data

    def validate_user_email(self, value):
        user_id = self.instance.user_id if self.instance else None
        if models.UserSecure.objects.filter(user_email=value).exclude(user_id=user_id).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_user_phone(self, value):
        user_id = self.instance.user_id if self.instance else None
        phones = [value, f"234{value}", f"2340{value}"]
        if models.UserSecure.objects.filter(user_phone__in=phones).exclude(user_id=user_id).exists():
            raise serializers.ValidationError("Phone number already exists with us.")
        return value

    def get_transactions(self, obj):
        transactions = models.UserTransactions.objects.filter(user=obj).order_by('-id')  # Sort by ID (latest first)
        return UserTransactionsSerializer(transactions, many=True, context=self.context).data

    def get_deposit_details(self, obj):
        deposit_qs = obj.deposit_details.all()
        deposit_qs = deposit_qs.filter(account_owner='owner')
        return BankDepositDetailsSerializer(deposit_qs, many=True).data

    def get_deposit_account(self, obj):
        deposit = obj.deposit_details.filter(account_owner='owner').first()
        if not deposit:
            deposit = obj.deposit_details.first()
        return BankDepositDetailsSerializer(deposit).data if deposit else None

class UserAIChatSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return localtime(obj.timestamp).isoformat()

    class Meta:
        model = models.UserAIChat
        fields = '__all__'
        extra_kwargs = {
            'user': {'write_only': True}
        }
