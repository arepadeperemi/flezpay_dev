import json
import traceback
import uuid
import os
from rest_framework import status
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from rest_framework.response import Response
from rest_framework.views import APIView
from api import models
from django.utils import timezone
from api.functions import misc, send_mail
from api.external.psb_api import PSB
from django.db import transaction
from api.models import BusinessDetails, UserSecure
from django.shortcuts import get_object_or_404
from api.user_data.data_views import calculate_total_balance, get_promo_context
from api.user_data.serializer import (
    UserSecureSerializer,
    UserDetailSerializer,
    UserCartItemsSerializer,
    UserItemsSerializer, UserBusinessDetailsSerializer
)
from api.external.kxpress_api import KxpressAPI
from api.external.custom_logistics_api import CustomLogisticsAPI
from rest_framework.permissions import IsAuthenticated
import logging


logger = logging.getLogger(__name__)

class SecureUpdate(APIView):

    def patch(self, request):
        try:
            user_id = misc.get_id(request)
            actual_user_id = getattr(request, 'actual_user_id', user_id)
            secure_instance = models.UserSecure.objects.get(user_id=actual_user_id)
            data = request.data.copy()

            user_phone = request.data.get('user_phone')
            if user_phone:
                pin = int(request.data['user_pin'])
                if not models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=user_phone).exists():
                    raise Exception('Pin is not valid or expired')
                
            password = request.data.get('user_pass')
            if password:
                if not secure_instance.check_password(password):
                    raise ValueError('Current password does not match')

                new_password = request.data.get('new_pass')
                if not new_password:
                    raise ValueError('New password is required')

                # Prevent setting the same password
                if secure_instance.check_password(new_password):
                    raise ValueError('Cannot set current password as new. Try another combination')

                secure_instance.set_password(new_password)
                secure_instance.save()
                
                # If manager, also sync to UserManagers
                if secure_instance.user_type == 'manager':
                    manager = models.UserManagers.objects.filter(manager_email__iexact=secure_instance.user_email).first()
                    if manager:
                        manager.password_changed = True
                        manager.manager_password = misc.hash_md5(misc.hash_md5(new_password))
                        manager.save()
                
            # Remove password fields from data so serializer doesn't try to save them
            data.pop('user_pass', None)
            data.pop('new_pass', None)

            serializer = UserSecureSerializer(secure_instance, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Data updated successfully"})

            for field, errors in serializer.errors.items():
                for error in errors:
                    raise Exception(error)
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


class DetailsUpdate(APIView):

    def patch(self, request):
        try:
            user_id = misc.get_id(request)
            actual_user_id = getattr(request, 'actual_user_id', user_id)
            instance = models.UserSecure.objects.get(user_id=actual_user_id)
            user, _ = models.UserDetails.objects.get_or_create(user=instance)

            # Profile details editing is disabled except for profile avatar
            if 'user_avatar' not in request.FILES:
                return Response({
                    'status': False,
                    'message': "Profile details editing is disabled. Only profile image updates are allowed."
                }, status=status.HTTP_400_BAD_REQUEST)

            data = {'user_avatar': request.FILES['user_avatar']}
            serializer = UserDetailSerializer(user, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                # If manager, also sync to UserManagers
                if instance.user_type == 'manager':
                    manager = models.UserManagers.objects.filter(manager_email__iexact=instance.user_email).first()
                    if manager:
                        manager.image = request.FILES['user_avatar']
                        manager.save()
                elif instance.user_type == 'staff':
                    staff = models.UserPayroll.objects.filter(user_id=instance).first()
                    if staff:
                        staff.image = request.FILES['user_avatar']
                        staff.save()

                return Response({'status': True, 'message': "Profile image updated successfully"})
            for field, errors in serializer.errors.items():
                for error in errors:
                    raise Exception(error)
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)
        

class CartItemUpdate(APIView):

    def patch(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            cart_item = models.UserCartItems.objects.get(user=instance, id=request.data['id'])
            cart_item.item_quantity = request.data['item_quantity']
            cart_item.save()
            return Response({'status': True, 'message': "Data updated successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)
        

class ProductUpdate(APIView):

    def patch(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'edit_stock'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'edit_stock' permission."}, status=status.HTTP_403_FORBIDDEN)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(instance).require_inventory()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


            item_id = request.data.get("id")
            if not item_id:
                return Response(
                    {"status": False, "message": "id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            item = models.UserItems.objects.get(user=instance, item_id=item_id)

            # Update basic fields
            item.item_name = request.data.get("item_name", item.item_name)
            item.item_serial_number = request.data.get("item_serial_number", item.item_serial_number)
            item.item_category = request.data.get("item_category", item.item_category)
            item.item_department = request.data.get("item_department", item.item_department)
            item.item_quantity = request.data.get("item_quantity", item.item_quantity)
            item.item_buy_amount = request.data.get("item_buy_amount", item.item_buy_amount)
            if "item_weight" in request.data:
                weight_val = request.data.get("item_weight")
                weight_unit = request.data.get("weight_unit") or request.data.get("item_weight_unit")
                canonical_unit = 'g' if (weight_unit and str(weight_unit).lower() in ['g', 'gram', 'grams']) else 'kg'
                if weight_val in (None, ""):
                    item.item_weight = None
                    # Keep the existing display unit preference when weight is cleared
                else:
                    try:
                        item.item_weight = round(float(weight_val), 4)
                    except (ValueError, TypeError):
                        pass
                item.item_weight_unit = canonical_unit
            item.item_colors = request.data.get("item_colors", item.item_colors)
            
            color_hex = request.data.get("color_hex", item.color_hex)
            item.color_hex = color_hex
            if color_hex:
                from api.user_data.colors import get_closest_color_name
                item.color_name = get_closest_color_name(color_hex)
            else:
                item.color_name = None
            if "item_amount" in request.data:
                try:
                    item.item_amount = request.data.get("item_amount")
                except Exception:
                    pass
            if "is_promo" in request.data:
                item.is_promo = str(request.data.get("is_promo")).lower() in ('true', '1')
            if "promo_percentage" in request.data or "promo_amount" in request.data:
                p_amt = request.data.get("promo_percentage")
                if p_amt in ('', None, 'null', 'undefined'):
                    p_amt = request.data.get("promo_amount")
                if p_amt in ('', None, 'null', 'undefined'):
                    item.promo_amount = None
                else:
                    try:
                        p_val = float(p_amt)
                        if 0 < p_val <= 100:
                            item.promo_amount = p_val
                        else:
                            item.promo_amount = None
                    except (ValueError, TypeError):
                        item.promo_amount = None
            if "in_store" in request.data:
                item.in_store = str(request.data.get("in_store")).lower() in ('true', '1')
            if "is_featured" in request.data:
                item.is_featured = str(request.data.get("is_featured")).lower() in ('true', '1')

            item.item_description = request.data.get("item_description", item.item_description)
            item.save()

            variants_str = request.data.get("variants")
            if variants_str is not None:
                import json
                from api.models import ProductVariant
                from api.user_data.colors import get_closest_color_name
                try:
                    variants_data = json.loads(variants_str)
                    existing_variants = {(v.variant_name or 'color', v.color_hex or '', v.size or ''): v for v in item.variants.all()}
                    seen_keys = set()
                    
                    for var in variants_data:
                        var_hex = var.get('color_hex') or ''
                        var_size = var.get('size') or ''
                        var_type = var.get('variant_name') or ('color' if var_hex else 'custom')
                        if not var_hex and not var_size:
                            continue

                        var_key = (var_type, var_hex, var_size)
                        seen_keys.add(var_key)
                        qty = int(var.get('quantity', 0))
                        var_price = var.get('price')
                        try:
                            var_price = float(var_price) if var_price not in (None, '', 0, '0') else None
                        except (ValueError, TypeError):
                            var_price = None
                        
                        if var_key in existing_variants:
                            v = existing_variants[var_key]
                            v.quantity = qty
                            v.price = var_price
                            v.save()
                        else:
                            var_name = var.get('color_name') or (get_closest_color_name(var_hex) if var_hex else '')
                            ProductVariant.objects.create(
                                product=item,
                                variant_name=var_type,
                                color_name=var_name if var_name else None,
                                color_hex=var_hex if var_hex else None,
                                size=var_size if var_size else None,
                                price=var_price,
                                quantity=qty
                            )
                    
                    for key, v in existing_variants.items():
                        if key not in seen_keys:
                            v.delete()
                except Exception as e:
                    pass

            # Handle Deleted Images
            deleted_images_str = request.data.get("deleted_images")
            if deleted_images_str:
                import json
                try:
                    deleted_images = json.loads(deleted_images_str)
                    models.ItemImages.objects.filter(item=item, id__in=deleted_images).delete()
                except Exception:
                    pass

            # Handle New Image Uploads
            # edit-product sends image_0, image_1, etc.
            max_images = 5
            current_image_count = models.ItemImages.objects.filter(item=item).count()
            image_keys = [k for k in request.FILES.keys() if k.startswith('image_') or k in ('image', 'images') or k.startswith('item_')]
            import re
            def get_img_sort_index(k):
                match = re.search(r'\d+', k)
                return int(match.group()) if match else 999
            image_keys.sort(key=get_img_sort_index)

            for key in image_keys:
                if current_image_count >= max_images:
                    break
                for up_img in request.FILES.getlist(key):
                    if current_image_count >= max_images:
                        break
                    models.ItemImages.objects.create(
                        item=item,
                        image=up_img
                    )
                    current_image_count += 1

            # Handle Digital Product / E-Book fields
            if "is_digital" in request.data:
                is_dig = request.data.get("is_digital")
                item.is_digital = str(is_dig).lower() in ('true', '1')
            if "digital_format" in request.data:
                item.digital_format = request.data.get("digital_format") or ''
            if "digital_file_name" in request.data:
                item.digital_file_name = request.data.get("digital_file_name") or ''
            if "digital_file_size" in request.data:
                item.digital_file_size = request.data.get("digital_file_size") or ''
            if "book_author" in request.data:
                item.book_author = request.data.get("book_author") or ''
            if "book_publisher" in request.data:
                item.book_publisher = request.data.get("book_publisher") or ''
            if "book_publication_date" in request.data:
                item.book_publication_date = request.data.get("book_publication_date") or ''
            if "book_isbn" in request.data:
                item.book_isbn = request.data.get("book_isbn") or ''
            if "book_pages" in request.data:
                val = request.data.get("book_pages")
                item.book_pages = int(val) if val not in (None, '', 'null') else None
            if "book_language" in request.data:
                item.book_language = request.data.get("book_language") or 'English'
            if "book_edition" in request.data:
                item.book_edition = request.data.get("book_edition") or ''
            if "book_reading_time" in request.data:
                item.book_reading_time = request.data.get("book_reading_time") or ''
            if "book_sample_text" in request.data:
                item.book_sample_text = request.data.get("book_sample_text") or ''
            if "book_series" in request.data:
                item.book_series = request.data.get("book_series") or ''

            if 'digital_file' in request.FILES:
                up_file = request.FILES['digital_file']
                item.digital_file = up_file
                if not item.digital_file_name:
                    item.digital_file_name = up_file.name
                size_mb = round(up_file.size / (1024 * 1024), 2)
                item.digital_file_size = f"{size_mb} MB" if size_mb >= 1 else f"{round(up_file.size / 1024, 1)} KB"
                if not item.digital_format:
                    item.digital_format = up_file.name.split('.')[-1].upper()
                item.is_digital = True

            if 'book_sample_file' in request.FILES:
                item.book_sample_file = request.FILES['book_sample_file']

            item.save()

            return Response(
                {"status": True, "message": "Item updated successfully"}
            )

        except models.UserItems.DoesNotExist:
            return Response(
                {"status": False, "message": "Item not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"status": False, "message": str(e), "traceback": traceback.format_exc()},
                status=status.HTTP_400_BAD_REQUEST
            )


class PriceAdjust(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = models.UserSecure.objects.get(user_id=user_id)

            items_data = request.data.get("items", [])

            for item_data in items_data:
                try:
                    item = models.UserItems.objects.get(user=user, id=item_data["item_id"])

                    item.item_amount = item_data.get("item_amount", item.item_amount)
                    item.is_promo = item_data.get("is_promo", item.is_promo)
                    if "promo_percentage" in item_data or "promo_amount" in item_data:
                        p_amt = item_data.get("promo_percentage")
                        if p_amt in ('', None, 'null', 'undefined'):
                            p_amt = item_data.get("promo_amount")
                        if p_amt in ('', None, 'null', 'undefined'):
                            item.promo_amount = None
                        else:
                            try:
                                p_val = float(p_amt)
                                if 0 < p_val <= 100:
                                    item.promo_amount = p_val
                                else:
                                    item.promo_amount = None
                            except (ValueError, TypeError):
                                item.promo_amount = None
                    item.last_adjusted_amount = item_data.get("last_adjusted_amount", item.last_adjusted_amount)
                    item.last_adjusted_date = item_data.get("last_adjusted_date", item.last_adjusted_date)

                    item.save()

                except models.UserItems.DoesNotExist:
                    continue

            return Response({'status': True, 'message': "Items updated successfully"})

        except Exception as e:
            error = str(e)
            if isinstance(e, KeyError):
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)
        



        



class AuthPinUpdate(APIView):

    def patch(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            trx = models.UserTrxPin.objects.get(user_details=instance)
            trx.account_pin = misc.hash_md5(misc.hash_md5(request.data['account_pin']))
            trx.save()
            return Response({'status': True, 'message': "Authentication pin updated successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)



class SubscriptionView(APIView):

    def post(self, request):
        user_id = misc.get_id(request)
        user = models.UserSecure.objects.get(user_id=user_id)

        data = request.data.copy()
        data['user'] = user.uniq_id

        plan_code = data.get('plan_code')
        duration = data.get('duration')

        if not plan_code or not duration:
            return Response(
                {"status": False, "message": "Plan and duration are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Ensure duration is integer
            try:
                duration = int(duration)
            except ValueError:
                return Response(
                    {"status": False, "message": "Invalid duration value"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch plan
            try:
                plan = models.SubscriptionPlans.objects.get(uniq_id=plan_code)
            except models.SubscriptionPlans.DoesNotExist:
                return Response(
                    {"status": False, "message": "Invalid plan selected"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 🔑 Calculate amount
            if duration == 1:
                total_amount = float(plan.one_amount)
            elif duration == 3:
                total_amount = float(plan.three_months)
            elif duration == 6:
                total_amount = float(plan.six_months)
            elif duration == 12:
                total_amount = float(plan.twelve_months)
            elif duration == 24:
                total_amount = float(plan.twelve_months) * 2  # 2 years
            else:
                return Response(
                    {"status": False, "message": "Unsupported duration"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate expiry date
            expiry_date = datetime.now() + relativedelta(months=duration)

            # Check balance
            balance = calculate_total_balance(user)
            if balance < total_amount:
                return Response(
                    {"status": False, "message": "Insufficient balance"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch or create business details
            instance = models.BusinessDetails.objects.filter(user=user).first()
            if instance:
                serializer = UserBusinessDetailsSerializer(instance, data=data, partial=True)
            else:
                serializer = UserBusinessDetailsSerializer(data=data)

            if serializer.is_valid():
                updated_instance = serializer.save()
                updated_instance.subscription_expiry = expiry_date
                updated_instance.save()
                with transaction.atomic():
                    withdraw = models.UserTransactions.objects.create(
                        user=user,
                        trx_status='completed',
                        trx_amount=total_amount,
                        trx_type='payment',
                        trx_currency="NGN",
                        description="Payment for subscription",
                        user_collection_id="",
                        destination_id=user.uniq_id
                    )

                    # Backup transaction
                    models.TransactionBackup.objects.create(
                        trx_uniq=withdraw,
                        trx_amount=total_amount,
                        trx_id=withdraw.trx_id,
                        sender=user.user_id,
                        recipient=user.user_id,
                        trx_currency="NGN",
                    )
                    models.Notifications.objects.create(
                        user=user,
                        title='Transfer',
                        description=f'You made payment for subscription',
                        notification_type='tranc_success'
                    )

                return Response(
                    {"status": True, "message": "Subscription successful"}
                )

            return Response(
                {"status": False, "message": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            return Response(
                {"status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyUserView(APIView):
    def post(self, request):
        data = request.data.copy()
        try:
            user = UserSecure.objects.get(user_email=data.get('email'))
            user_details = models.UserDetails.objects.get(user=user)
            verification = user.verification.last()  # get latest record

            if not verification:
                return Response({'status': False, 'message': 'No verification details found.'})

            user.is_verified = True
            user.save(update_fields=["is_verified"])
            timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

            send_mail.mailSender(
                'account_verified.html',
                'Account verification',
                [user.user_email],
                {
                    "user_name": user_details.first_name,
                    "verification_date": timestamp
                }
            )

            return Response({'status': True, 'message': "User verified successfully"})

        except UserSecure.DoesNotExist:
            return Response({'status': False, 'message': 'User not found'})


class DeclineVerificationView(APIView):
    def post(self, request):
        data = request.data.copy()
        try:
            user = UserSecure.objects.get(user_email=data.get('email'))
            user_details = models.UserDetails.objects.get(user=user)
            verification = user.verification.last()  # get latest record

            if not verification:
                return Response({'status': False, 'message': 'No verification details to decline.'})

            verification.delete()
            timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

            send_mail.mailSender(
                'account_declined.html',
                'Verification declined',
                [user.user_email],
                {
                    "user_name": user_details.first_name,
                    "verification_date": timestamp
                }
            )

            return Response({'status': True, 'message': "Verification details declined and deleted"})

        except UserSecure.DoesNotExist:
            return Response({'status': False, 'message': 'User not found'})

class StoreSetupView(APIView):
    """Create or update BusinessDetails store configuration (wizard + settings)."""

    STORE_SETUP_ALIASES = {
        'delivery_type': 'store_delivery_type',
        'withdrawal_account_id': 'store_payment_collection',
        'instant_settlement': 'store_instant_settlement',
        'store_layout': 'store_layout_template',
        'accent_color': 'store_accent_color',
    }

    BOOL_FIELDS = ('store_setup', 'store_instant_settlement', 'is_published', 'enable_ai_calls', 'enable_auto_payroll', 'enable_payroll_otp', 'enable_loyalty', 'enable_livechat', 'enable_whatsapp', 'store_promo_enabled', 'hide_store_name', 'hide_hot_products', 'developer_mode_enabled', 'store_delivery_pay_on_delivery', 'store_delivery_pay_instantly')
    JSON_FIELDS = ('store_countries', 'store_operating_hours', 'store_pickup_locations', 'store_authors')

    def _normalize_store_setup_payload(self, data):
        """Map wizard field names to model fields; never treat profile avatar as store logo."""
        if hasattr(data, 'dict'):
            data = data.dict()
        else:
            data = dict(data)

        for old_key, new_key in self.STORE_SETUP_ALIASES.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)

        data.pop('user_avatar', None)
        # We no longer sync business_image and store_logo. They are separate fields.

        for field in self.BOOL_FIELDS:
            if field in data:
                val = data[field]
                if isinstance(val, str):
                    data[field] = val.strip().lower() in ('true', '1', 'yes', 'on')

        for field in self.JSON_FIELDS:
            if field in data and isinstance(data[field], str) and data[field].strip():
                try:
                    data[field] = json.loads(data[field])
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
        
        if 'store_delivery_base_fee' in data:
            try:
                data['store_delivery_base_fee'] = float(data['store_delivery_base_fee'])
            except (ValueError, TypeError):
                data['store_delivery_base_fee'] = 0.0

        if 'store_delivery_fee_per_weight' in data:
            try:
                data['store_delivery_fee_per_weight'] = float(data['store_delivery_fee_per_weight'])
            except (ValueError, TypeError):
                data['store_delivery_fee_per_weight'] = 0.0

        return data

    def post(self, request):
        try:
            user_id = None
            try:
                user_id = misc.get_id(request)
            except Exception:
                user_id = None
            if not user_id and request.user and request.user.is_authenticated:
                user_id = getattr(request.user, 'user_id', None)
                request.actual_user_id = user_id
            if not user_id:
                return Response({'status': False, 'message': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
            if not misc.enforce_permissions(request, 'manage_online_store'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_online_store' permission."}, status=status.HTTP_403_FORBIDDEN)
            user = models.UserSecure.objects.get(user_id=user_id)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(user).require_online_store()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            data = self._normalize_store_setup_payload(request.data)

            # ── Check premium store layout permissions ──
            if 'store_layout_template' in data:
                requested_layout = str(data['store_layout_template']).strip().lower()
                if requested_layout in ('luxe-horizon', 'vanguard-atelier'):
                    from api.models import user_has_purchased_layout
                    user_owner = misc.get_owner_from_user(user)
                    if not user_has_purchased_layout(user_owner, requested_layout):
                        return Response({
                            'status': False,
                            'message': 'You must purchase this premium theme before activating it.'
                        }, status=status.HTTP_403_FORBIDDEN)

            for key, uploaded in request.FILES.items():
                if hasattr(uploaded, 'name') and uploaded.name:
                    _, ext = os.path.splitext(uploaded.name)
                    uploaded.name = f"{uuid.uuid4().hex}{ext}"
                data[key] = uploaded

            clear_logo = data.pop('clear_business_image', None)
            should_clear_logo = clear_logo in (True, 'true', 'True', '1', 'yes', 'on')
            
            clear_banner = data.pop('clear_store_banner', None)
            should_clear_banner = clear_banner in (True, 'true', 'True', '1', 'yes', 'on')

            instance = models.BusinessDetails.objects.filter(user=user).first()
            if not instance:
                user_country_code = models.UserDetails.objects.filter(user=user).values_list('user_country', flat=True).first() or 'NG'
                allowed_country = models.AllowedCountries.objects.filter(code=user_country_code).first()
                country_vat = allowed_country.vat_percentage if (allowed_country and allowed_country.vat_percentage is not None) else 0.0
                instance = models.BusinessDetails.objects.create(user=user, vat_percentage=country_vat)

            was_setup = instance.store_setup

            # ── Capture old store_domain before save for change detection ──
            old_store_domain = instance.store_domain or ''

            if 'business_name' in data:
                data['store_name'] = data['business_name']
            elif 'store_name' in data:
                data['business_name'] = data['store_name']

            # ── Validate store_domain before saving ──
            if 'store_slug' in data:
                from django.conf import settings as django_settings
                target_domain = getattr(django_settings, 'CLOUDFLARE_TARGET_DOMAIN', '')
                if target_domain and data.get('store_slug'):
                    slug = data['store_slug'].strip().lower()
                    if slug:
                        data['store_domain'] = f"{slug}.{target_domain}"
                elif not data.get('store_slug'):
                    data['store_domain'] = ''

            new_store_domain = data.get('store_domain', '').strip() if data.get('store_domain') else ''
            if new_store_domain:
                # Validate format and extract subdomain
                domain_valid, domain_err = self._validate_store_domain(new_store_domain, user)
                if not domain_valid:
                    return Response({'status': False, 'message': domain_err}, status=status.HTTP_400_BAD_REQUEST)

            serializer = UserBusinessDetailsSerializer(
                instance,
                data=data,
                partial=True,
                context={'request': request},
            )
            if serializer.is_valid():
                instance = serializer.save()
                
                if instance.store_setup and not was_setup:
                    from api.tasks import check_store_setup_followup_task, send_store_created_instant_email_task
                    send_store_created_instant_email_task.apply_async(args=[user_id])
                    check_store_setup_followup_task.apply_async(args=[user_id], countdown=86400)

                update_fields = []
                if should_clear_logo and not request.FILES.get('business_image'):
                    instance.business_image = None
                    update_fields.append('business_image')
                if should_clear_banner and not request.FILES.get('store_banner'):
                    instance.store_banner = None
                    update_fields.append('store_banner')
                if request.FILES.get('featured_author_image_file'):
                    from django.core.files.storage import default_storage
                    photo_file = request.FILES.get('featured_author_image_file')
                    raw_ext = photo_file.name.split('.')[-1].lower() if '.' in photo_file.name else 'jpg'
                    ext = raw_ext if raw_ext in ['jpg', 'jpeg', 'png', 'webp', 'gif'] else 'jpg'
                    filename = f"store_authors/author_{instance.id}_{uuid.uuid4().hex[:8]}.{ext}"
                    saved_path = default_storage.save(filename, photo_file)
                    instance.store_featured_author_image = default_storage.url(saved_path)
                    update_fields.append('store_featured_author_image')
                elif data.get('clear_featured_author_image') in (True, 'true', 'True', '1'):
                    instance.store_featured_author_image = ''
                    update_fields.append('store_featured_author_image')
                if update_fields:
                    instance.save(update_fields=update_fields)

                # ── Prime Instagram Social Gallery Cache in Background ──
                if instance.store_social_instagram:
                    try:
                        from api.services.instagram_service import validate_instagram_url
                        is_valid_ig, ig_username, _ = validate_instagram_url(instance.store_social_instagram)
                        if is_valid_ig and ig_username:
                            from api.tasks import refresh_instagram_gallery_task
                            refresh_instagram_gallery_task.delay(instance.id, ig_username)
                    except Exception as e:
                        logger.warning(f"Could not trigger Instagram cache prime: {e}")

                # ── Cloudflare DNS Management ──
                current_store_domain = instance.store_domain or ''
                if current_store_domain != old_store_domain:
                    self._handle_store_domain_change(user_id, old_store_domain, current_store_domain)

                banner_url = instance.store_banner.url if instance.store_banner else ''
                logo_url = instance.business_image.url if instance.business_image else ''

                return Response({
                    "status": True,
                    "message": "Store setup updated successfully",
                    "store_banner_url": banner_url,
                    "business_image_url": logo_url
                })
            return Response({"status": False, "message": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        except models.UserSecure.DoesNotExist:
            return Response({"status": False, "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _validate_store_domain(store_domain, user):
        """
        Validate the store_domain value:
        - Must be a valid subdomain of CLOUDFLARE_TARGET_DOMAIN
        - Must not be a reserved subdomain
        - Must be unique (not used by another business)

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        import re
        from django.conf import settings as django_settings
        from api.external.cloudflare_dns import CloudflareDNS

        target_domain = getattr(django_settings, 'CLOUDFLARE_TARGET_DOMAIN', '')
        if not target_domain:
            return False, 'Store domain configuration is not available. Please contact support.'

        store_domain = store_domain.strip().lower()

        # Extract subdomain from full domain
        subdomain = CloudflareDNS.extract_subdomain(store_domain)
        if not subdomain:
            # Allow passing just the subdomain part too
            if '.' not in store_domain and re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', store_domain):
                subdomain = store_domain
            else:
                return False, f'Store domain must be a subdomain of {target_domain} (e.g. yourstore.{target_domain})'

        # Validate subdomain format
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', subdomain):
            return False, 'Invalid subdomain. Only lowercase letters, numbers, and hyphens are allowed.'

        if len(subdomain) > 63:
            return False, 'Subdomain cannot exceed 63 characters.'

        # Check reserved subdomains
        reserved = getattr(django_settings, 'RESERVED_SUBDOMAINS', set())
        if subdomain in reserved:
            return False, f'The subdomain "{subdomain}" is reserved and cannot be used.'

        # Check uniqueness — no other business should use this domain
        full_domain = f'{subdomain}.{target_domain}'
        existing = models.BusinessDetails.objects.filter(
            store_domain__in=[full_domain, subdomain]
        ).exclude(user=user).first()
        if existing:
            return False, 'This store domain is already taken. Please choose a different one.'

        return True, None

    @staticmethod
    def _handle_store_domain_change(user_id, old_domain, new_domain):
        """
        Handle Cloudflare DNS updates when store_domain changes.

        - If domain was set/changed: dispatch update task for the new domain
        - If old domain existed: dispatch remove task to clean up old DNS record
        """
        from django.conf import settings as django_settings
        from api.external.cloudflare_dns import CloudflareDNS
        from api.tasks import update_cloudflare_dns_task, remove_cloudflare_dns_task
        import logging

        logger = logging.getLogger(__name__)
        target_domain = getattr(django_settings, 'CLOUDFLARE_TARGET_DOMAIN', '')

        if not target_domain:
            logger.warning('CLOUDFLARE_TARGET_DOMAIN is not configured. Skipping DNS management.')
            return

        # Extract subdomain from old domain
        old_subdomain = None
        if old_domain:
            old_subdomain = CloudflareDNS.extract_subdomain(old_domain)
            if not old_subdomain and '.' not in old_domain:
                old_subdomain = old_domain.strip().lower()

        # Extract subdomain from new domain
        new_subdomain = None
        if new_domain:
            new_subdomain = CloudflareDNS.extract_subdomain(new_domain)
            if not new_subdomain and '.' not in new_domain:
                new_subdomain = new_domain.strip().lower()

        # Remove old DNS record if the subdomain actually changed
        if old_subdomain and old_subdomain != new_subdomain:
            logger.info('Scheduling removal of old Cloudflare DNS: %s', old_subdomain)
            remove_cloudflare_dns_task.delay(user_id, old_subdomain)

        # Create/update new DNS record
        if new_subdomain:
            logger.info('Scheduling Cloudflare DNS update: %s', new_subdomain)
            update_cloudflare_dns_task.delay(user_id, new_subdomain)


class StaffStatusUpdate(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'edit_cashier'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'edit_cashier' permission."}, status=status.HTTP_403_FORBIDDEN)
            user = models.UserSecure.objects.get(user_id=user_id)
            staff_id = request.data.get('id')
            new_status = request.data.get('status') # 'active' or 'suspended'

            if not staff_id or not new_status:
                return Response({'status': False, 'message': 'Staff ID and status are required'}, status=status.HTTP_400_BAD_REQUEST)

            staff = get_object_or_404(models.UserSecure, business_owner=user, uniq_id=staff_id)
            staff.is_active = (new_status == 'active')
            staff.save()

            return Response({'status': True, 'message': f'Staff account {new_status} successfully'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class DepartmentUpdate(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = models.UserSecure.objects.get(user_id=user_id)
            dept_id = request.data.get('department_id')
            new_name = request.data.get('department_name')
            new_desc = request.data.get('description')

            if not dept_id or not new_name:
                return Response({'status': False, 'message': 'ID and name are required'}, status=status.HTTP_400_BAD_REQUEST)

            dept = get_object_or_404(models.CashierDepartments, user=user, uniq_id=dept_id)
            old_name = dept.department_name
            dept.department_name = new_name
            if new_desc is not None:
                dept.description = new_desc
            dept.save()

            # Sync with Staff and Managers
            models.UserPayroll.objects.filter(user_id=user, department=old_name).update(department=new_name)
            models.UserManagers.objects.filter(user=user, manager_department=old_name).update(manager_department=new_name)

            return Response({'status': True, 'message': 'Department updated and synced successfully'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CategoryUpdate(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = models.UserSecure.objects.get(user_id=user_id)
            cat_id = request.data.get('category_id')
            new_name = request.data.get('category_name')
            new_desc = request.data.get('description')

            if not cat_id or not new_name:
                return Response({'status': False, 'message': 'ID and name are required'}, status=status.HTTP_400_BAD_REQUEST)

            cat = get_object_or_404(models.ProductCategories, user=user, uniq_id=cat_id)
            old_name = cat.category_name
            cat.category_name = new_name
            if new_desc is not None:
                cat.description = new_desc
            cat.save()

            # Sync with UserItems
            models.UserItems.objects.filter(user=user, item_category=old_name).update(item_category=new_name)

            return Response({'status': True, 'message': 'Category updated and synced successfully'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class StoreItemsSyncView(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'manage_online_store'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_online_store' permission."}, status=status.HTTP_403_FORBIDDEN)
            user = models.UserSecure.objects.get(user_id=user_id)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(user).require_online_store()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            action = request.data.get('action')

            if action == 'add':
                item_ids = request.data.get('item_ids', [])
                models.UserItems.objects.filter(user=user, item_id__in=item_ids).update(in_store=True, is_featured=True)
                return Response({'status': True, 'message': 'Items added to store'})
            
            elif action == 'remove':
                item_ids = request.data.get('item_ids', [])
                models.UserItems.objects.filter(user=user, item_id__in=item_ids).update(in_store=False, is_featured=False)
                return Response({'status': True, 'message': 'Items removed from store'})

            elif action == 'featured':
                item_id = request.data.get('item_id')
                is_featured = request.data.get('is_featured', False)
                models.UserItems.objects.filter(user=user, item_id=item_id).update(is_featured=is_featured)
                return Response({'status': True, 'message': 'Item featured status updated'})

            return Response({'status': False, 'message': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class StaffDetailsUpdate(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'edit_cashier'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'edit_cashier' permission."}, status=status.HTTP_403_FORBIDDEN)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            staff_id = request.data.get('id')
            
            staff_user = get_object_or_404(models.UserSecure, business_owner=user, uniq_id=staff_id)
            staff = staff_user.payroll_profile.first()
            staff_details = staff_user.details.first()
            
            # Update Payroll fields
            if request.data.get('account_name') or request.data.get('account_number') or request.data.get('bank_name'):
                if not staff:
                    # Create payroll profile if it doesn't exist
                    staff = models.UserPayroll.objects.create(
                        user_id=user,
                        staff_user=staff_user,
                        account_name=request.data.get('account_name', ''),
                        account_number=request.data.get('account_number', ''),
                        bank_name=request.data.get('bank_name', '')
                    )
                else:
                    if request.data.get('account_name'):
                        staff.account_name = request.data.get('account_name')
                    if request.data.get('account_number'):
                        staff.account_number = request.data.get('account_number')
                    if request.data.get('bank_name'):
                        staff.bank_name = request.data.get('bank_name')
                    staff.save()
                
            # Update UserSecure fields
            user_secure_changed = False
            if request.data.get('email'):
                new_email = request.data.get('email').strip().lower()
                if new_email and new_email != staff_user.user_email.lower():
                    if models.UserSecure.objects.filter(user_email__iexact=new_email).exists():
                        return Response({'status': False, 'message': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
                staff_user.user_email = new_email
                user_secure_changed = True
            if request.data.get('phone'):
                phone_str = str(request.data.get('phone')).replace('+', '').replace(' ', '').replace('-', '')
                if phone_str.isdigit():
                    staff_user.user_phone = int(phone_str)
                    user_secure_changed = True
            
            if user_secure_changed:
                staff_user.save()

            # Update UserDetails fields
            if not staff_details:
                staff_details = models.UserDetails.objects.create(user=staff_user)

            if staff_details:
                details_changed = False
                if request.data.get('first_name'):
                    staff_details.first_name = request.data.get('first_name')
                    details_changed = True
                if request.data.get('last_name'):
                    staff_details.last_name = request.data.get('last_name')
                    details_changed = True
                if request.data.get('job_title'):
                    staff_details.job_title = request.data.get('job_title')
                    details_changed = True
                if request.data.get('department'):
                    staff_details.department = request.data.get('department')
                    details_changed = True
                    
                # Boolean fields for permissions
                if 'pos_access' in request.data:
                    staff_details.pos_access = request.data.get('pos_access')
                    details_changed = True
                if 'can_apply_discounts' in request.data:
                    staff_details.can_apply_discounts = request.data.get('can_apply_discounts')
                    details_changed = True
                if 'can_process_refunds' in request.data:
                    staff_details.can_process_refunds = request.data.get('can_process_refunds')
                    details_changed = True
                if 'can_view_reports' in request.data:
                    staff_details.can_view_reports = request.data.get('can_view_reports')
                    details_changed = True
                    
                if details_changed:
                    staff_details.save()

            # Handle Image / Avatar Upload (multipart file or base64)
            avatar_file = request.FILES.get('user_avatar') or request.FILES.get('image')
            if avatar_file and staff_details:
                staff_details.user_avatar = avatar_file
                staff_details.save()
                if staff:
                    staff.image = avatar_file
                    staff.save()
            else:
                image_data = request.data.get('image_base64') or request.data.get('user_avatar_base64')
                if image_data and isinstance(image_data, str) and ';base64,' in image_data and staff_details:
                    import base64
                    from django.core.files.base import ContentFile
                    fmt, imgstr = image_data.split(';base64,')
                    ext = fmt.split('/')[-1] if '/' in fmt else 'png'
                    file_content = ContentFile(base64.b64decode(imgstr), name=f"avatar_{staff_user.uniq_id}.{ext}")
                    staff_details.user_avatar = file_content
                    staff_details.save()
                    if staff:
                        staff.image = file_content
                        staff.save()

            avatar_url = None
            if staff_details and staff_details.user_avatar:
                try:
                    avatar_url = staff_details.user_avatar.url
                except Exception:
                    pass

            return Response({
                'status': True, 
                'message': 'Staff details updated successfully.',
                'image': avatar_url
            })
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AssignCollectionAccount(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            staff_id = request.data.get('id')
            
            staff_user = get_object_or_404(models.UserSecure, business_owner=user, uniq_id=staff_id)
            
            # Check if a collection account already exists
            existing = models.BankDepositDetails.objects.filter(user=user, account_reference=str(staff_user.uniq_id)).first()
            if existing:
                return Response({'status': False, 'message': 'Collection account already exists.'})
                
            # Create a mock Paystack DVA (In production, hit Paystack API here)
            import random
            mock_account_num = ''.join([str(random.randint(0, 9)) for _ in range(10)])
            mock_bank = "Paystack-Titan"
            
            user_details = staff_user.details.first()
            full_name = f"{user_details.first_name} {user_details.last_name}" if user_details else staff_user.user_email
            
            new_collection = models.BankDepositDetails.objects.create(
                user=user,
                account_owner="staff",
                account_reference=str(staff_user.uniq_id),
                bank_name=mock_bank,
                account_name=full_name,
                account_number=mock_account_num
            )
            
            return Response({'status': True, 'message': 'Collection account created and assigned.'})
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class SendStaffEmail(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            staff_id = request.data.get('id')
            subject = request.data.get('subject')
            message = request.data.get('message')
            
            staff = get_object_or_404(models.UserSecure, business_owner=user, uniq_id=staff_id)
            
            user_details = user.details.first()
            business_name = f"{user_details.first_name} {user_details.last_name}" if user_details else "FlezPay System"
            
            context = {
                'business_name': business_name,
                'message': message,
            }
            send_mail.mailSender('staff_message.html', subject, [staff.user_email], context=context)
            
            return Response({'status': True, 'message': 'Email sent successfully.'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ResetStaffPassword(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user = get_object_or_404(models.UserSecure, user_id=user_id)
            staff_id = request.data.get('id')
            
            staff_user = get_object_or_404(models.UserSecure, business_owner=user, uniq_id=staff_id)
            
            import string, random
            chars = string.ascii_letters + string.digits + "@#$"
            temp_pwd = ''.join(random.choice(chars) for _ in range(8))
            
            staff_user.set_password(temp_pwd)
            staff_user.save()
            
            return Response({'status': True, 'message': 'Password reset successful.', 'new_password': temp_pwd})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

def send_customer_order_receipt_async(invoice_id):
    try:
        invoice = models.UserInvoices.objects.filter(invoice_id=invoice_id).first()
        if not invoice:
            return
            
        business = models.BusinessDetails.objects.filter(user=invoice.user_id).first()
        if not business:
            return
            
        invoice_items = invoice.invoice_items.all()
        items_data = []
        subtotal = 0.0
        tax = 0.0
        delivery_fee = 0.0
        
        has_digital_items = False
        has_physical_items = False
        attachments = []
        digital_downloads = []

        from api.functions.digital_downloads import generate_digital_download_token
        import mimetypes
        from django.conf import settings
        site_domain = os.environ.get('SITE_DOMAIN', 'localhost:8000')
        protocol = 'https' if not settings.DEBUG else 'http'
        
        for i_item in invoice_items:
            if i_item.item_id == 'TAX_001':
                tax = float(i_item.item_amount)
            elif i_item.item_id == 'DELIVERY_001':
                delivery_fee = float(i_item.item_amount)
            else:
                # Regular product item
                total_price = float(i_item.item_amount) * i_item.item_quantity
                subtotal += total_price
                
                # Fetch image & product model
                base_item = models.UserItems.objects.filter(item_id=i_item.item_id).first()
                image_url = None
                is_item_digital = bool(base_item and base_item.is_digital)

                if base_item:
                    first_image = base_item.images.first()
                    if first_image and first_image.image:
                        try:
                            image_url = first_image.image.url
                        except Exception:
                            pass
                
                if is_item_digital:
                    has_digital_items = True
                    # Digital product: create download token & link
                    token = generate_digital_download_token(invoice, base_item)
                    download_url = f"{protocol}://{site_domain}/api/digital-products/download/{token}/"
                    
                    file_name = base_item.digital_file_name or (os.path.basename(base_item.digital_file.name) if base_item.digital_file else 'Download')
                    digital_downloads.append({
                        'name': base_item.item_name,
                        'file_name': file_name,
                        'download_url': download_url,
                        'file_size': base_item.digital_file_size or ''
                    })
                    
                    # Attach downloadable file to email upon payment
                    if base_item.digital_file:
                        try:
                            fname = base_item.digital_file_name or os.path.basename(base_item.digital_file.name)
                            mtype, _ = mimetypes.guess_type(fname)
                            mtype = mtype or 'application/octet-stream'
                            file_bytes = None
                            
                            if hasattr(base_item.digital_file, 'path') and os.path.exists(base_item.digital_file.path):
                                if os.path.getsize(base_item.digital_file.path) <= 25 * 1024 * 1024:
                                    with open(base_item.digital_file.path, 'rb') as f:
                                        file_bytes = f.read()
                            else:
                                base_item.digital_file.open('rb')
                                file_bytes = base_item.digital_file.read()
                                base_item.digital_file.close()
                                
                            if file_bytes and len(file_bytes) <= 25 * 1024 * 1024:
                                attachments.append((fname, file_bytes, mtype))
                        except Exception as attach_err:
                            print(f"Error attaching digital file to email: {attach_err}")
                else:
                    has_physical_items = True

                items_data.append({
                    'name': i_item.item_name,
                    'quantity': i_item.item_quantity,
                    'color_name': i_item.color_name,
                    'size': i_item.size,
                    'total_price': total_price,
                    'image_url': image_url,
                    'is_digital': is_item_digital
                })
                
        grand_total = subtotal + tax + delivery_fee
        currency = invoice.user_id.details.first().currency if invoice.user_id.details.exists() else 'NGN'
        currency_symbol = '₦' if currency == 'NGN' else '$' if currency == 'USD' else currency
        
        context = {
            'store_name': business.store_name,
            'customer_name': invoice.customer_name,
            'customer_phone': invoice.customer_phone,
            'customer_email': invoice.customer_email,
            'delivery_address': invoice.delivery_address,
            'delivery_state': invoice.delivery_state,
            'delivery_country': invoice.delivery_country,
            'invoice_id': invoice.invoice_id,
            'items': items_data,
            'subtotal': subtotal,
            'tax': tax,
            'delivery_fee': delivery_fee,
            'grand_total': grand_total,
            'currency': currency_symbol,
            'has_digital_items': has_digital_items,
            'has_physical_items': has_physical_items,
            'digital_downloads': digital_downloads,
        }
        
        if invoice.customer_email:
            send_mail.mailSenderAsync(
                template='store_order_receipt.html',
                subject=f"Your Order Receipt - {business.store_name}",
                to=[invoice.customer_email],
                context=context,
                attachments=attachments
            )
    except Exception as e:
        print(f"Failed to send order receipt email: {e}")


class ProcessStoreCheckoutView(APIView):
    def post(self, request):
        try:
            store_slug = request.data.get('store_slug')
            cart = request.data.get('cart', [])
            delivery = request.data.get('delivery', {})
            
            business = models.BusinessDetails.objects.filter(store_slug=store_slug).first()
            if not business:
                return Response({'status': False, 'message': 'Store not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            user = business.user
            
            payment_method = request.data.get('payment_method', 'card')
            
            # 1. Validate Payment Method
            if payment_method == 'card':
                if not business.store_delivery_pay_instantly:
                    return Response({'status': False, 'message': 'Instant payment is not enabled for this store.'}, status=status.HTTP_400_BAD_REQUEST)
            elif payment_method == 'pod':
                if not business.store_delivery_pay_on_delivery:
                    return Response({'status': False, 'message': 'Pay on Delivery is not enabled for this store.'}, status=status.HTTP_400_BAD_REQUEST)
            elif payment_method == 'arc_usdc':
                pass  # Arc USDC — invoice created here, payment session created by arc_payments app
            else:
                return Response({'status': False, 'message': 'Invalid payment method.'}, status=status.HTTP_400_BAD_REQUEST)
                
            # 1.5 Validate System Delivery Payment Config
            user_details = user.details.first() if user else None
            merchant_country = user_details.user_country if user_details else 'NG'
            country_config = models.AllowedCountries.objects.filter(code=merchant_country).first()
            if country_config:
                if payment_method == 'pod' and not country_config.system_delivery_pod_enabled:
                    return Response({'status': False, 'message': 'Pay on Delivery is not available in your region.'}, status=status.HTTP_400_BAD_REQUEST)
                if business.store_delivery_type == 'system':
                    if payment_method == 'card' and not country_config.system_delivery_card_enabled:
                        return Response({'status': False, 'message': 'Card payment is not available for system deliveries in this region.'}, status=status.HTTP_400_BAD_REQUEST)
            if not cart or not isinstance(cart, list) or len(cart) == 0:
                return Response({'status': False, 'message': 'Your cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

            from api.user_data.inventory_helpers import resolve_matching_variant
            from django.db.models import Sum

            # Pre-validate cart items, variants, and stock before creating invoice to avoid orphan empty invoices
            validated_cart_items = []
            for item in cart:
                real_item_id = str(item.get('original_id') or item.get('id', '')).split('_')[0]
                item_obj = models.UserItems.objects.filter(user=user, item_id=real_item_id).first()
                if not item_obj:
                    return Response({'status': False, 'message': f"Item '{item.get('name', 'Product')}' is not available."}, status=status.HTTP_400_BAD_REQUEST)

                quantity = int(item.get('quantity', 1))
                if quantity <= 0:
                    return Response({'status': False, 'message': f"Invalid quantity for {item_obj.item_name}."}, status=status.HTTP_400_BAD_REQUEST)

                color_hex = item.get('color_hex')
                color_name = item.get('color_name') or item.get('color')
                size = item.get('size') or item.get('option') or item.get('custom_option') or item.get('variant')

                # Fallback recovery if size or option was embedded in ID or cart item name
                raw_id = str(item.get('id', ''))
                if not size and '_' in raw_id:
                    parts = raw_id.split('_')
                    for p in parts[1:]:
                        v_match = item_obj.variants.filter(size__iexact=p).first()
                        if v_match:
                            size = v_match.size
                            break
                if not size:
                    raw_name = str(item.get('name', ''))
                    for v in item_obj.variants.all():
                        if v.size and f"({v.size})" in raw_name:
                            size = v.size
                            break

                variant = None
                has_variants = item_obj.variants.exists()
                if has_variants:
                    variant = resolve_matching_variant(
                        item_obj,
                        color_name=color_name,
                        color_hex=color_hex,
                        size=size
                    )
                    if not variant:
                        return Response({
                            'status': False, 
                            'message': f"Please select an option for {item_obj.item_name}."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    if variant.quantity < quantity:
                        variant_desc = f"{variant.color_name} - {variant.size}" if (variant.color_name and variant.size) else (variant.color_name or variant.size or "Selected option")
                        return Response({
                            'status': False, 
                            'message': f"'{item_obj.item_name} ({variant_desc})' is out of stock or only {variant.quantity} available."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    color_name = color_name or variant.color_name
                    color_hex = color_hex or variant.color_hex
                    size = size or variant.size
                else:
                    if (item_obj.item_quantity or 0) < quantity:
                        return Response({
                            'status': False, 
                            'message': f"'{item_obj.item_name}' is out of stock or only {item_obj.item_quantity} available."
                        }, status=status.HTTP_400_BAD_REQUEST)

                validated_cart_items.append({
                    'item': item,
                    'item_obj': item_obj,
                    'quantity': quantity,
                    'variant': variant,
                    'color_name': color_name,
                    'color_hex': color_hex,
                    'size': size,
                    'has_variants': has_variants
                })

            # Check if all items are digital products
            is_all_digital = len(validated_cart_items) > 0 and all(
                getattr(val['item_obj'], 'is_digital', False) for val in validated_cart_items
            )

            # Prevent Pay on Delivery for digital orders
            if is_all_digital and payment_method == 'pod':
                return Response({'status': False, 'message': 'Pay on Delivery is not available for digital products. Please select instant payment.'}, status=status.HTTP_400_BAD_REQUEST)

            # Generate invoice ID
            invoice_id = f"INV-{uuid.uuid4().hex[:12].upper()}"

            with transaction.atomic():
                # Create Invoice
                delivery_addr = delivery.get('address') or ('Digital Delivery' if is_all_digital else '')
                invoice = models.UserInvoices.objects.create(
                    user_id=user,
                    invoice_id=invoice_id,
                    invoice_status='pending',
                    invoice_type='instant',
                    customer_name=delivery.get('name'),
                    customer_email=delivery.get('email'),
                    customer_phone=delivery.get('phone'),
                    is_online_order=True,
                    delivery_status='pending',
                    delivery_address=delivery_addr,
                    delivery_country=delivery.get('country'),
                    delivery_state=delivery.get('state'),
                    delivery_lga=delivery.get('lga'),
                    delivery_postal_code=delivery.get('postal_code'),
                    delivery_type=business.store_delivery_type,
                    invoice_payment_type=payment_method
                )
                
                promo_context = get_promo_context(business)
                promo_multiplier = 1.0
                if promo_context.get('promo_active') and promo_context.get('promo_percentage'):
                    promo_multiplier = (100 - float(promo_context['promo_percentage'])) / 100.0

                subtotal = 0.0
                total_weight = 0.0

                for val_item in validated_cart_items:
                    item = val_item['item']
                    item_obj = val_item['item_obj']
                    quantity = val_item['quantity']
                    variant = val_item['variant']
                    color_name = val_item['color_name']
                    color_hex = val_item['color_hex']
                    size = val_item['size']
                    has_variants = val_item['has_variants']

                    # Stock is NOT deducted here — deduction happens only when payment is confirmed (completed).
                    
                    base_price = float(variant.price) if (variant and variant.price is not None) else float(item_obj.item_amount or 0)
                    price = base_price * promo_multiplier
                    
                    subtotal += price * quantity
                    
                    # Exclude digital items from delivery weight
                    if not getattr(item_obj, 'is_digital', False):
                        item_weight = getattr(item_obj, 'item_weight', item.get('weight', 0))
                        total_weight += float(item_weight or 0) * quantity
                    
                    models.UserInvoiceItems.objects.create(
                        user=invoice,
                        item_invoice_id=invoice.invoice_id,
                        item_id=item_obj.item_id,
                        item_name=item_obj.item_name,
                        item_amount=price,
                        item_buy_amount=item_obj.item_buy_amount or 0.00,
                        item_quantity=quantity,
                        color_name=color_name,
                        color_hex=color_hex,
                        size=size
                    )
            
            # Calculate backend tax and delivery
            vat_pct = float(getattr(business, 'vat_percentage', 0) or 0)
            calculated_tax = subtotal * (vat_pct / 100.0)
            
            # Delivery fee is completely excluded (0.00) for digital products
            calculated_delivery = 0.0
            if not is_all_digital:
                if business.store_delivery_type == 'self':
                    base_fee = float(business.store_delivery_base_fee or 0)
                    fee_per_weight = float(business.store_delivery_fee_per_weight or 0)
                    calculated_delivery = base_fee + (total_weight * fee_per_weight)
                elif business.store_delivery_type == 'system':
                    try:
                        user_country = user.details.first().user_country if user.details.exists() else 'NG'
                        if user_country == 'NG':
                            from api.external.kxpress_api import KxpressAPI
                            client = KxpressAPI()
                        else:
                            from api.external.custom_logistics_api import CustomLogisticsAPI
                            client = CustomLogisticsAPI()
                            
                        from_state = business.store_pickup_state
                        from_lga = business.store_pickup_lga
                        to_state = delivery.get('state_id') or delivery.get('state')
                        to_lga = delivery.get('lga_id') or delivery.get('lga')
                        
                        if from_state and from_lga and to_state and to_lga:
                            calc_response = client.calculate_shipping(from_state, from_lga, to_state, to_lga, max(1.0, total_weight))
                            if calc_response.get('status') and 'data' in calc_response:
                                data_val = calc_response.get('data', {})
                                ngn_amount = data_val.get('data') if isinstance(data_val, dict) else 0
                                if not ngn_amount and isinstance(data_val, dict):
                                    ngn_amount = data_val.get('totalAmount', 0)
                                ngn_amount = float(ngn_amount) if ngn_amount else 0.0
                                
                                from api.models import UserSecure
                                admin_settings = UserSecure.objects.filter(is_superuser=True).first().admin_settings or {}
                                markup_val = admin_settings.get('system_delivery_markup_ngn')
                                markup_ngn = float(markup_val) if markup_val is not None else 200.0
                                ngn_amount += markup_ngn
                                
                                user_currency = user.details.first().currency if user.details.exists() else 'NGN'
                                if user_currency != 'NGN':
                                    from api.user_data.domain_views import get_exchange_rate
                                    rate = get_exchange_rate(base_currency='NGN', target_currency=user_currency)
                                    if rate:
                                        calculated_delivery = ngn_amount * float(rate)
                                    else:
                                        calculated_delivery = ngn_amount
                                else:
                                    calculated_delivery = ngn_amount
                    except Exception as e:
                        print("Error calculating system shipping:", e)
                    
                    # Fallback: if backend calculation returned 0 but frontend sent a valid amount,
                    # use the frontend-provided delivery_amount (already includes markup from /api/delivery/calculate)
                    if calculated_delivery == 0.0:
                        frontend_delivery = float(delivery.get('delivery_amount', 0))
                        if frontend_delivery > 0:
                            calculated_delivery = frontend_delivery

            models.UserInvoiceItems.objects.create(
                user=invoice,
                item_invoice_id=invoice.invoice_id,
                item_id='TAX_001',
                item_name=f'Estimated Tax ({vat_pct}%)',
                item_amount=calculated_tax,
                item_quantity=1
            )
            
            models.UserInvoiceItems.objects.create(
                user=invoice,
                item_invoice_id=invoice.invoice_id,
                item_id='DELIVERY_001',
                item_name='Digital Delivery (Free)' if is_all_digital else 'Delivery Fee',
                item_amount=0.0 if is_all_digital else calculated_delivery,
                item_quantity=1
            )
            
            # Generate Waybill if Pay on Delivery and System managed (physical items only)
            if payment_method == 'pod' and not is_all_digital:
                if business.store_delivery_type == 'system':
                    from api.functions.logistics import process_store_waybill
                    process_store_waybill(invoice)
                
                send_customer_order_receipt_async(invoice_id)

            return Response({'status': True, 'message': 'Checkout successful', 'invoice_id': invoice_id})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

from api.external.paystack_api import PaystackAPI

class VerifyStorePaymentView(APIView):
    def post(self, request):
        try:
            invoice_id = request.data.get('invoice_id')
            reference = request.data.get('reference')
            
            if not invoice_id or not reference:
                return Response({'status': False, 'message': 'Missing invoice_id or reference'}, status=400)
                
            invoice = models.UserInvoices.objects.filter(invoice_id=invoice_id).first()
            if not invoice:
                return Response({'status': False, 'message': 'Invoice not found'}, status=404)
                
            if invoice.invoice_status == 'completed':
                return Response({'status': True, 'message': 'Invoice already paid'})

            paystack = PaystackAPI()
            verify_response = paystack.verify_transaction(reference)
            
            if verify_response.get('status') and verify_response.get('data', {}).get('status') == 'success':
                invoice.invoice_status = 'completed'
                invoice.delivery_status = 'processing'
                invoice.save(update_fields=['invoice_status', 'delivery_status'])
                
                # Deduct stock now that payment is confirmed
                from api.user_data.inventory_helpers import deduct_invoice_stock
                deduct_invoice_stock(invoice)
                
                # Deduct delivery fee from amount paid for system-managed deliveries
                amount_paid = float(verify_response.get('data', {}).get('amount', 0)) / 100.0
                currency = verify_response.get('data', {}).get('currency', 'NGN')
                amount_to_credit = amount_paid
                
                if invoice.delivery_type == 'system':
                    delivery_item = invoice.invoice_items.filter(item_id='DELIVERY_001').first()
                    delivery_fee = float(delivery_item.item_amount) if delivery_item else 0.0
                    amount_to_credit = max(0.0, amount_paid - delivery_fee)
                    
                    # Generate Waybill if System managed and order has physical items
                    has_physical_items = False
                    for inv_item in invoice.invoice_items.exclude(item_id__in=['TAX_001', 'DELIVERY_001']):
                        b_item = models.UserItems.objects.filter(item_id=inv_item.item_id).first()
                        if b_item and not b_item.is_digital:
                            has_physical_items = True
                            break
                    if has_physical_items:
                        from api.functions.logistics import process_store_waybill
                        process_store_waybill(invoice)
                
                # Credit the store owner's wallet
                models.UserTransactions.objects.create(
                    user=invoice.user_id,
                    trx_status='completed',
                    trx_amount=amount_to_credit,
                    trx_currency=currency,
                    trx_type='credit',
                    description=f"Payment for Order #{invoice.invoice_id} via Paystack",
                    trx_source='paystack',
                    user_collection_id='0',
                    destination_id='0'
                )
                
                # Notify the merchant
                models.Notifications.objects.create(
                    user=invoice.user_id,
                    title="New Order Paid",
                    description=f"Order #{invoice.invoice_id} has been paid ({currency}{amount_paid:,.2f}). Please fulfil it.",
                    notification_type="tranc_success",
                    action_url=f"/online-orders/{invoice.invoice_id}"
                )
                
                # Send email to merchant
                from api.functions import send_mail
                invoice_items = list(invoice.invoice_items.all())
                send_mail.mailSenderAsync(
                    "merchant_new_order.html", 
                    f"New Online Order #{invoice.invoice_id}", 
                    [invoice.user_id.user_email], 
                    {"invoice": invoice, "invoice_items": invoice_items, "amount": amount_paid, "currency": currency}
                )
                
                send_customer_order_receipt_async(invoice_id)
                
                return Response({'status': True, 'message': 'Payment verified successfully'})
            else:
                return Response({'status': False, 'message': 'Payment verification failed'}, status=400)
                
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=500)

class UpdateDeliveryStatusView(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            invoice_id = request.data.get('invoice_id')
            status = request.data.get('status')
            
            if not invoice_id or not status:
                return Response({'status': False, 'message': 'Missing invoice_id or status'}, status=400)
                
            # user_id belongs to UserSecure, we must get the user instance
            user = models.UserSecure.objects.get(user_id=user_id)
            invoice = models.UserInvoices.objects.filter(invoice_id=invoice_id, user_id=user).first()
            if not invoice:
                return Response({'status': False, 'message': 'Invoice not found'}, status=404)
                
            invoice.delivery_status = status
            invoice.save()
            
            if status == 'delivered' and invoice.customer_email:
                business = models.BusinessDetails.objects.filter(user=user).first()
                
                # Generate review tokens for each item
                review_tokens = []
                invoice_items = models.UserInvoiceItems.objects.filter(user=invoice)
                for inv_item in invoice_items:
                    # Need to get the actual UserItems instance
                    try:
                        import uuid
                        uuid_obj = uuid.UUID(inv_item.item_id)
                        actual_item = models.UserItems.objects.filter(item_id=uuid_obj).first()
                    except (ValueError, TypeError, AttributeError):
                        actual_item = None
                        
                    if actual_item:
                        token = models.ReviewToken.objects.create(
                            item=actual_item,
                            invoice=invoice,
                            customer_name=invoice.customer_name,
                            customer_email=invoice.customer_email
                        )
                        
                        image_url = actual_item.images.first().image.url if actual_item.images.first() else None
                        if image_url and not image_url.startswith('http'):
                            image_url = f"{request.scheme}://{request.get_host()}{image_url}"
                            
                        review_tokens.append({
                            'token': token,
                            'item_name': inv_item.item_name,
                            'image': image_url
                        })

                context = {
                    'invoice': invoice,
                    'business': business,
                    'host': f"{request.scheme}://{request.get_host()}",
                    'review_tokens': review_tokens
                }
                send_mail.mailSender('order_delivered.html', f"Your order #{invoice.invoice_id} has been delivered", [invoice.customer_email], context=context)
            
            return Response({'status': True, 'message': 'Delivery status updated successfully'})
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=500)

class MarkNotificationRead(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not user_id:
                return Response({'status': False, 'message': 'Unauthorized'}, status=401)
            
            user = models.UserSecure.objects.get(user_id=user_id)
            notification_id = request.data.get('notification_id')
            mark_all = request.data.get('mark_all', False)

            if mark_all:
                models.Notifications.objects.filter(user=user, is_read=False).update(is_read=True)
                return Response({'status': True, 'message': 'All notifications marked as read'})
            
            if notification_id:
                notification = models.Notifications.objects.filter(user=user, id=notification_id).first()
                if notification:
                    notification.is_read = True
                    notification.save()
                    return Response({'status': True, 'message': 'Notification marked as read'})
                return Response({'status': False, 'message': 'Notification not found'}, status=404)

            return Response({'status': False, 'message': 'Missing parameters'}, status=400)
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=500)

class UpdatePaymentStatusView(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            invoice_id = request.data.get('invoice_id')
            status_val = request.data.get('status')
            
            if not invoice_id or not status_val:
                return Response({'status': False, 'message': 'Missing invoice_id or status'}, status=400)
                
            user = models.UserSecure.objects.get(user_id=user_id)
            invoice = models.UserInvoices.objects.filter(invoice_id=invoice_id, user_id=user).first()
            if not invoice:
                return Response({'status': False, 'message': 'Invoice not found'}, status=404)
                
            prev_status = invoice.invoice_status
            invoice.invoice_status = status_val
            invoice.save(update_fields=['invoice_status'])
            
            if status_val == 'completed' and prev_status != 'completed':
                from api.user_data.inventory_helpers import deduct_invoice_stock
                deduct_invoice_stock(invoice)
            
            return Response({'status': True, 'message': 'Payment status updated successfully'})
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=500)

class UpdateTutorialStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            user = request.user
            if not isinstance(user.admin_settings, dict):
                user.admin_settings = {}
            
            user.admin_settings['tutorial_seen'] = True
            user.save()
            return Response({'status': True, 'message': 'Tutorial status updated'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=500)


class SubmitReviewView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request):
        try:
            token_id = request.data.get('token')
            rating = request.data.get('rating')
            review_text = request.data.get('review_text')
            reviewer_name = request.data.get('reviewer_name')

            if not token_id or not rating or not reviewer_name:
                return Response({'status': False, 'message': 'Missing required fields'}, status=400)
            
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    return Response({'status': False, 'message': 'Rating must be between 1 and 5'}, status=400)
            except ValueError:
                return Response({'status': False, 'message': 'Invalid rating'}, status=400)

            token = models.ReviewToken.objects.filter(id=token_id).first()
            if not token:
                return Response({'status': False, 'message': 'Invalid review token'}, status=404)
            
            if token.is_used:
                return Response({'status': False, 'message': 'This review link has already been used'}, status=400)
            
            # Create the review
            models.ProductReview.objects.create(
                item=token.item,
                reviewer_name=reviewer_name,
                reviewer_email=token.customer_email,
                rating=rating,
                body=review_text,
                is_verified_buyer=True,
                is_approved=True
            )

            # Mark token as used
            token.is_used = True
            token.save()

            return Response({'status': True, 'message': 'Review submitted successfully!'})

        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=500)
