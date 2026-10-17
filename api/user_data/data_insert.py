import re

import random
import traceback
import uuid
from datetime import datetime
import os
import requests
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

class UnsafeSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return None
from api import models
from api.functions import misc, send_mail
from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
from api.models import UserItems, UserVerificationDetails, UserPayroll, UserInvoices, UserInvoiceItems, \
    BusinessDetails
from api.external import psb_api, paystack_api
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import serializers
from api.user_data.serializer import (
    UserItemsSerializer,
    UserCartItemsSerializer,
    UserWithdrawalAccountSerializer, CryptoAssetsSerializer, CryptoAssetChainsSerializer, UserVerificationSerializer,
    BankDepositDetailsSerializer, UserPayrollSerializer, UserInvoicesSerializer, UserBusinessDetailsSerializer,
    DepartmentsSerializer, UserManagersSerializer, SubscriptionSerializer, ProductCategoriesSerializer
)


@method_decorator(csrf_exempt, name='dispatch')
class AddItems(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'add_stock'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'add_stock' permission."}, status=status.HTTP_403_FORBIDDEN)
            account_instance = models.UserSecure.objects.get(user_id=user_id)
            
            # Check plan limits
            sub_manager = SubscriptionManager(account_instance)
            sub_manager.require_inventory()
            
            # Extract data. It can be JSON or FormData with 'payload' and files
            data_list = request.data
            if 'payload' in request.data:
                import json
                try:
                    data_list = json.loads(request.data['payload'])
                except Exception:
                    pass

            current_count = models.UserItems.objects.filter(user=account_instance).count()
            adding_count = len(data_list) if isinstance(data_list, list) else 1
            
            try:
                sub_manager.check_max_products(current_count, adding_count)
            except SubscriptionLimitError as e:
                return Response({
                    'status': False,
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

            for req_item in data_list:
                raw_w = req_item.get('item_weight')
                w_unit = req_item.get('weight_unit') or req_item.get('item_weight_unit')
                # Normalise to a canonical unit value ('g' or 'kg', default 'kg')
                canonical_unit = 'g' if (w_unit and str(w_unit).lower() in ['g', 'gram', 'grams']) else 'kg'
                req_item['item_weight_unit'] = canonical_unit
                if raw_w not in (None, ''):
                    try:
                        req_item['item_weight'] = round(float(raw_w), 4)
                    except (ValueError, TypeError):
                        pass
                elif raw_w == '':
                    req_item['item_weight'] = None

            serializer = UserItemsSerializer(data=data_list, many=True)
            if serializer.is_valid():
                from api.user_data.colors import get_closest_color_name
                from api.models import ProductVariant, ItemImages
                from django.db import transaction
                
                items_data = serializer.validated_data
                
                with transaction.atomic():
                    for i, req_item in enumerate(data_list):
                        item_data = items_data[i]
                        
                        if item_data.get('color_hex'):
                            item_data['color_name'] = get_closest_color_name(item_data['color_hex'])
                            
                        item_instance = UserItems.objects.create(user=account_instance, **item_data)
                        
                        variants = req_item.get('variants', [])
                        variants_to_create = []
                        for var in variants:
                            var_hex = var.get('color_hex') or None
                            var_name = var.get('color_name') or None
                            var_size = var.get('size') or None
                            var_type = var.get('variant_name') or ('color' if var_hex else 'custom')
                            if var_hex and not var_name:
                                var_name = get_closest_color_name(var_hex)

                            var_price = var.get('price')
                            try:
                                var_price = float(var_price) if var_price not in (None, '', 0, '0') else None
                            except (ValueError, TypeError):
                                var_price = None

                            variants_to_create.append(ProductVariant(
                                product=item_instance,
                                variant_name=var_type,
                                color_name=var_name,
                                color_hex=var_hex,
                                size=var_size,
                                price=var_price,
                                quantity=int(var.get('quantity', 0))
                            ))

                        if variants_to_create:
                            ProductVariant.objects.bulk_create(variants_to_create)
                            
                        # Handle Image uploads for this batch index
                        # Images come as item_{i}_image_{j}
                        for key in request.FILES:
                            if key.startswith(f'item_{i}_image_'):
                                ItemImages.objects.create(
                                    item=item_instance,
                                    image=request.FILES[key]
                                )

                        # Handle Digital Product and Sample uploads for this batch index
                        digital_file_key = f'item_{i}_digital_file'
                        if digital_file_key in request.FILES:
                            dig_file = request.FILES[digital_file_key]
                            item_instance.digital_file = dig_file
                            if not item_instance.digital_file_name:
                                item_instance.digital_file_name = dig_file.name
                            if not item_instance.digital_file_size:
                                size_mb = round(dig_file.size / (1024 * 1024), 2)
                                item_instance.digital_file_size = f"{size_mb} MB" if size_mb >= 1 else f"{round(dig_file.size / 1024, 1)} KB"
                            if not item_instance.digital_format:
                                item_instance.digital_format = dig_file.name.split('.')[-1].upper()
                            item_instance.is_digital = True
                            item_instance.save()
                        elif 'digital_file' in request.FILES and i == 0:
                            dig_file = request.FILES['digital_file']
                            item_instance.digital_file = dig_file
                            if not item_instance.digital_file_name:
                                item_instance.digital_file_name = dig_file.name
                            if not item_instance.digital_file_size:
                                size_mb = round(dig_file.size / (1024 * 1024), 2)
                                item_instance.digital_file_size = f"{size_mb} MB" if size_mb >= 1 else f"{round(dig_file.size / 1024, 1)} KB"
                            if not item_instance.digital_format:
                                item_instance.digital_format = dig_file.name.split('.')[-1].upper()
                            item_instance.is_digital = True
                            item_instance.save()

                        sample_file_key = f'item_{i}_sample_file'
                        if sample_file_key in request.FILES:
                            item_instance.book_sample_file = request.FILES[sample_file_key]
                            item_instance.save()
                        elif 'book_sample_file' in request.FILES and i == 0:
                            item_instance.book_sample_file = request.FILES['book_sample_file']
                            item_instance.save()

                return Response({'status': True, 'message': "Product(s) added successfully"})

            raise Exception(serializer.errors)

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)








class AddToCart(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            data = request.data.copy()
            data['user'] = instance.uniq_id
            
            item_id = data.get('item_id')
            item = models.UserItems.objects.filter(item_id=item_id).first()
            if not item:
                raise Exception("Item not found")
                
            qty = int(data.get('item_quantity', 1))
            
            variants = item.variants.all()
            if variants.exists():
                color_hex = data.get('color_hex')
                size = data.get('size')
                if not color_hex and not size:
                    raise Exception("Please select a variant option")
                
                if color_hex and size:
                    variant = variants.filter(color_hex=color_hex, size__iexact=size).first()
                elif color_hex:
                    variant = variants.filter(color_hex=color_hex, size__isnull=True).first()
                    if not variant:
                        variant = variants.filter(color_hex=color_hex, size="").first()
                    if not variant:
                        variant = variants.filter(color_hex=color_hex).first()
                elif size:
                    variant = variants.filter(size__iexact=size).first()
                    if not variant:
                        variant = variants.filter(size=size).first()
                else:
                    variant = None

                if not variant:
                    raise Exception("Selected variant does not exist")
                
                if variant.quantity < qty:
                    raise Exception("Not enough stock for the selected variant")
                
                data['color_name'] = variant.color_name
                data['color_hex'] = variant.color_hex
                data['size'] = variant.size
            else:
                if item.item_quantity < qty:
                    raise Exception("Not enough stock")
            
            serializer = UserCartItemsSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Item added to cart successfully"})
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



class AddWithdrawalAccount(APIView):

    def post(self, request):
        try:
            api = paystack_api.PaystackAPI()

            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_finances'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_finances' permission."}, status=status.HTTP_403_FORBIDDEN)
            instance = models.UserSecure.objects.get(user_id=user_id)
            data = request.data.copy()
            data['withdrawal_unique'] = instance.uniq_id

            api_response = api.create_transfer_recipient(
                name=data.get('account_name'),
                account_number=data.get('account_number'),
                bank_code=data.get('bank_code')
            )

            if not api_response.get("status"):
                raise Exception(api_response.get("message"))

            api_response_data = api_response.get('data')

            if not api_response_data or not api_response_data.get("recipient_code"):
                raise Exception("Failed to retrieve Paystack recipient code")

            data['paystack_recipient_code'] = api_response_data.get('recipient_code')
            data["paystack_reference"] = f"PR-{uuid.uuid4().hex[:12].upper()}"

            serializer = UserWithdrawalAccountSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Bank details added successfully"})
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


class AddCryptoAsset(APIView):

    def post(self, request):
        try:
            data = request.data.copy()
            serializer = CryptoAssetsSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Asset added successfully"})
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

    def delete(self, request):
        try:
            asset_id = request.data.get('asset_id') or request.query_params.get('asset_id')
            if not asset_id:
                raise KeyError('asset_id')

            instance = models.CryptoAssets.objects.filter(asset_id=asset_id)
            if not instance.exists():
                raise Exception("Asset not found")

            instance.delete()
            return Response({'status': True, 'message': "Asset deleted successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


class AddCryptoAssetChain(APIView):

    def post(self, request):
        try:
            data = request.data.copy()
            instance = models.CryptoAssets.objects.filter(asset_id=data['asset'])
            if not instance.exists():
                raise Exception('Invalid asset')

            data['asset'] = instance.first().crypto_uniq_id

            serializer = CryptoAssetChainsSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Asset chain added successfully"})
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

    def delete(self, request):
        try:
            chain_id = request.data.get('chain_id') or request.query_params.get('chain_id')
            if not chain_id:
                raise KeyError('chain_id')

            instance = models.CryptoAssetChains.objects.filter(chain_id=chain_id)
            if not instance.exists():
                raise Exception("Asset chain not found")

            instance.delete()
            return Response({'status': True, 'message': "Asset chain deleted successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)



def process_myaza_kyc_verification(kyc_record, user_instance, files_dict=None):
    """
    Submits KYC details to Myaza Trust API for automated government-backed validation.
    Handles media uploads (selfie, document), creates verification, and updates record status.
    """
    from api.external.myaza_api import MyazaTrustAPI
    from api.tasks import check_user_dual_verification
    from api.models import UserDetails
    import logging
    import time

    logger = logging.getLogger(__name__)
    client = MyazaTrustAPI()

    if not client.publishable_key and not client.secret_key:
        logger.info("Myaza API keys not configured; keeping verification for manual review.")
        return

    media_ids = {}

    # Upload selfie if provided
    selfie_file = (files_dict or {}).get('kyc_user_image') or (files_dict or {}).get('user_image')
    if selfie_file:
        try:
            selfie_bytes = selfie_file.read()
            selfie_file.seek(0)
            res_upload = client.upload_media(selfie_bytes, getattr(selfie_file, 'name', 'selfie.jpg'), media_type='selfie')
            if res_upload.get('status') and res_upload.get('media_id'):
                media_ids['selfie'] = res_upload['media_id']
        except Exception as e:
            logger.warning(f"Failed to upload selfie to Myaza: {e}")

    # Upload document front if provided
    doc_file = (files_dict or {}).get('kyc_driver_licence') or (files_dict or {}).get('driver_licence')
    if doc_file:
        try:
            doc_bytes = doc_file.read()
            doc_file.seek(0)
            res_upload = client.upload_media(doc_bytes, getattr(doc_file, 'name', 'document.jpg'), media_type='documentFront')
            if res_upload.get('status') and res_upload.get('media_id'):
                media_ids['documentFront'] = res_upload['media_id']
        except Exception as e:
            logger.warning(f"Failed to upload ID document to Myaza: {e}")

    # Prepare user data
    user_details = UserDetails.objects.filter(user=user_instance).first()
    user_data = {}
    first_name = kyc_record.first_name or (user_details.first_name if user_details else None)
    last_name = kyc_record.last_name or (user_details.last_name if user_details else None)
    if first_name:
        user_data['firstName'] = first_name
    if last_name:
        user_data['lastName'] = last_name
    if kyc_record.date_of_birth:
        try:
            user_data['dob'] = kyc_record.date_of_birth.strftime('%Y-%m-%d')
        except Exception:
            user_data['dob'] = str(kyc_record.date_of_birth)

    # Submit verification
    res_verify = client.submit_verification(
        country='NG',
        id_type=kyc_record.verification_id or 'nin',
        id_number=kyc_record.legal_id,
        user_data=user_data or None,
        media_ids=media_ids or None,
        external_user_id=user_instance.user_id,
    )

    if not res_verify.get('status'):
        logger.warning(f"Myaza verification submission failed: {res_verify.get('message')}")
        msg = str(res_verify.get('message', ''))
        if 'only_test_ids_allowed' in msg:
            kyc_record.reason = "Provider: In Sandbox mode, only designated test IDs are accepted (e.g. 00000000001)."
            kyc_record.verification_status = '2'
            kyc_record.save(update_fields=['verification_status', 'reason'])
            user_instance.kyc_verified = False
            user_instance.save(update_fields=['kyc_verified'])
            check_user_dual_verification(user_instance)
        return

    ver_id = res_verify.get('verification_id')
    kyc_record.provider_reference = ver_id
    kyc_record.save(update_fields=['provider_reference'])

    # In sandbox or fast databases, status may resolve in 1-2 seconds. Check immediate status:
    time.sleep(1.5)
    stat_res = client.get_status(ver_id)

    if stat_res.get('status'):
        myaza_status = str(stat_res.get('myaza_status') or '').lower()
        check_status = str(stat_res.get('check_status') or '').lower()

        if myaza_status in ['approved'] or check_status in ['verified']:
            kyc_record.verification_status = '1'
            kyc_record.reason = ''
            kyc_record.save(update_fields=['verification_status', 'reason'])

            user_instance.kyc_verified = True
            user_instance.save(update_fields=['kyc_verified'])

            try:
                from api.functions.verification_sync import sync_verified_identity_from_provider
                sync_verified_identity_from_provider(kyc_record, payload_data=stat_res, client=client)
            except Exception as sync_err:
                logger.error(f"Error syncing verified identity in immediate KYC check: {sync_err}")

            check_user_dual_verification(user_instance)
            try:
                from api.functions.verification_emails import send_tier_verification_email
                send_tier_verification_email(user=user_instance, tier_type='KYC', new_status='1')
            except Exception:
                pass
            logger.info(f"Myaza KYC immediately approved for user {user_instance.user_email}")

        elif myaza_status in ['failed', 'declined', 'not_found'] or check_status in ['failed', 'not_found']:
            kyc_record.verification_status = '2'
            data = stat_res.get('data') or {}
            reason = data.get('reason') or data.get('reasonCode') or 'Verification declined by identity registry'
            kyc_record.reason = f"Provider: {reason}"
            kyc_record.save(update_fields=['verification_status', 'reason'])

            user_instance.kyc_verified = False
            user_instance.save(update_fields=['kyc_verified'])
            check_user_dual_verification(user_instance)
            try:
                from api.functions.verification_emails import send_tier_verification_email
                send_tier_verification_email(user=user_instance, tier_type='KYC', new_status='2', reason=reason)
            except Exception:
                pass
            logger.info(f"Myaza KYC declined for user {user_instance.user_email}: {reason}")


@method_decorator(csrf_exempt, name='dispatch')
class UserVerificationView(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            data = request.data
            
            # Check if this is a dual submission with kyc_* and/or kyb_* fields
            has_kyc_fields = any(k.startswith('kyc_') for k in data.keys()) or any(k.startswith('kyc_') for k in request.FILES.keys())
            has_kyb_fields = any(k.startswith('kyb_') for k in data.keys()) or any(k.startswith('kyb_') for k in request.FILES.keys())

            if has_kyc_fields or has_kyb_fields:
                saved_types = []
                locked_types = []
                errors = []

                # Process KYC
                if has_kyc_fields:
                    existing_kyc = UserVerificationDetails.objects.filter(user=instance, verification_type='KYC').first()
                    if existing_kyc and existing_kyc.verification_status in ['0', '1']:
                        locked_types.append('KYC')
                    else:
                        kyc_first_name = (data.get('kyc_first_name') or data.get('first_name') or '').strip()
                        kyc_last_name = (data.get('kyc_last_name') or data.get('last_name') or '').strip()
                        kyc_dob = data.get('kyc_dob') or data.get('date_of_birth') or None
                        if kyc_dob == '':
                            kyc_dob = None

                        kyc_data = {
                            'user': instance.uniq_id,
                            'verification_type': 'KYC',
                            'account_type': 'individual',
                            'verification_id': data.get('kyc_verification_id', ''),
                            'legal_id': data.get('kyc_legal_id', ''),
                            'user_address': data.get('kyc_user_address', ''),
                            'first_name': kyc_first_name or None,
                            'last_name': kyc_last_name or None,
                            'date_of_birth': kyc_dob,
                            'verification_status': '0',
                            'reason': ''
                        }
                        if 'kyc_driver_licence' in request.FILES:
                            kyc_data['driver_licence'] = request.FILES['kyc_driver_licence']
                        if 'kyc_proof_of_address' in request.FILES:
                            kyc_data['proof_of_address'] = request.FILES['kyc_proof_of_address']
                        if 'kyc_user_image' in request.FILES:
                            kyc_data['user_image'] = request.FILES['kyc_user_image']

                        if existing_kyc:
                            serializer = UserVerificationSerializer(existing_kyc, data=kyc_data, partial=True)
                        else:
                            serializer = UserVerificationSerializer(data=kyc_data)

                        if serializer.is_valid():
                            saved_kyc = serializer.save()

                            # Update user first and last names with data provided on verification
                            user_details = models.UserDetails.objects.filter(user=instance).first()
                            if user_details:
                                up_fields = []
                                if kyc_first_name:
                                    user_details.first_name = kyc_first_name
                                    up_fields.append('first_name')
                                if kyc_last_name:
                                    user_details.last_name = kyc_last_name
                                    up_fields.append('last_name')
                                if up_fields:
                                    user_details.save(update_fields=up_fields)

                            process_myaza_kyc_verification(saved_kyc, instance, files_dict=request.FILES)
                            saved_types.append('KYC')
                        else:
                            errors.append(f"KYC validation failed: {serializer.errors}")

                # Process KYB
                if has_kyb_fields:
                    existing_kyb = UserVerificationDetails.objects.filter(user=instance, verification_type='KYB').first()
                    if existing_kyb and existing_kyb.verification_status in ['0', '1']:
                        locked_types.append('KYB')
                    else:
                        kyb_data = {
                            'user': instance.uniq_id,
                            'verification_type': 'KYB',
                            'account_type': 'business',
                            'verification_id': data.get('kyb_verification_id', ''),
                            'legal_id': data.get('kyb_legal_id', ''),
                            'user_address': data.get('kyb_user_address', ''),
                            'verification_status': '0',
                            'reason': ''
                        }
                        if 'kyb_driver_licence' in request.FILES:
                            kyb_data['driver_licence'] = request.FILES['kyb_driver_licence']
                        if 'kyb_proof_of_address' in request.FILES:
                            kyb_data['proof_of_address'] = request.FILES['kyb_proof_of_address']
                        if 'kyb_user_image' in request.FILES:
                            kyb_data['user_image'] = request.FILES['kyb_user_image']

                        if existing_kyb:
                            serializer = UserVerificationSerializer(existing_kyb, data=kyb_data, partial=True)
                        else:
                            serializer = UserVerificationSerializer(data=kyb_data)

                        if serializer.is_valid():
                            serializer.save()
                            saved_types.append('KYB')
                        else:
                            errors.append(f"KYB validation failed: {serializer.errors}")

                if errors:
                    return Response({'status': False, 'message': '; '.join(errors)}, status=status.HTTP_400_BAD_REQUEST)

                if not saved_types and locked_types:
                    return Response({
                        'status': False,
                        'message': f"{' and '.join(locked_types)} verification is already pending or verified and cannot be edited until rejected."
                    }, status=status.HTTP_400_BAD_REQUEST)

                return Response({
                    'status': True,
                    'message': f"{' and '.join(saved_types)} details submitted successfully for review."
                })

            # Single submission fallback (using verification_type)
            v_type = data.get('verification_type', 'KYC')
            existing = UserVerificationDetails.objects.filter(user=instance, verification_type=v_type).first()
            if existing and existing.verification_status in ['0', '1']:
                status_label = 'under review' if existing.verification_status == '0' else 'already verified'
                return Response({
                    'status': False,
                    'message': f"{v_type} verification is currently {status_label} and cannot be edited until rejected."
                }, status=status.HTTP_400_BAD_REQUEST)

            record_data = data.copy()
            record_data['user'] = instance.uniq_id
            record_data['verification_status'] = '0'
            record_data['reason'] = ''

            if v_type == 'KYC':
                if 'kyc_first_name' in record_data and not record_data.get('first_name'):
                    record_data['first_name'] = record_data.get('kyc_first_name')
                if 'kyc_last_name' in record_data and not record_data.get('last_name'):
                    record_data['last_name'] = record_data.get('kyc_last_name')
                if 'kyc_dob' in record_data and not record_data.get('date_of_birth'):
                    record_data['date_of_birth'] = record_data.get('kyc_dob') or None

            if existing:
                serializer = UserVerificationSerializer(existing, data=record_data, partial=True)
            else:
                serializer = UserVerificationSerializer(data=record_data)

            if serializer.is_valid():
                saved_rec = serializer.save()
                if v_type == 'KYC':
                    fn = (record_data.get('first_name') or record_data.get('kyc_first_name') or '').strip()
                    ln = (record_data.get('last_name') or record_data.get('kyc_last_name') or '').strip()
                    user_details = models.UserDetails.objects.filter(user=instance).first()
                    if user_details:
                        up_fields = []
                        if fn:
                            user_details.first_name = fn
                            up_fields.append('first_name')
                        if ln:
                            user_details.last_name = ln
                            up_fields.append('last_name')
                        if up_fields:
                            user_details.save(update_fields=up_fields)

                    process_myaza_kyc_verification(saved_rec, instance, files_dict=request.FILES)
                return Response({"status": True, "message": f"{v_type} verification details submitted successfully."})
            raise Exception(serializer.errors)

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            v_type = request.data.get('verification_type', 'KYC')
            verification_instance = UserVerificationDetails.objects.filter(user=instance, verification_type=v_type).first()
            if not verification_instance:
                verification_instance = UserVerificationDetails.objects.filter(user=instance).first()

            if not verification_instance:
                return Response({'status': False, 'message': 'Verification record not found.'}, status=status.HTTP_404_NOT_FOUND)

            if verification_instance.verification_status in ['0', '1']:
                return Response({
                    'status': False,
                    'message': 'Verification details cannot be modified while pending review or verified.'
                }, status=status.HTTP_400_BAD_REQUEST)

            data = request.data.copy()
            data['verification_status'] = '0'
            data['reason'] = ''
            serializer = UserVerificationSerializer(verification_instance, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"status": True, "message": "Verification details updated successfully."},
                                status=status.HTTP_200_OK)
            for field, errors in serializer.errors.items():
                for error in errors:
                    raise Exception(f"{field}: {error}")
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class UserVerificationSessionView(APIView):
    """
    Creates or retrieves a Myaza Trust Verification Session URL
    for the SDK Widget (either KYC or KYB workflow).
    """
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]

    def post(self, request):
        try:
            from django.conf import settings
            from api.external.myaza_api import MyazaTrustAPI

            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            step = (request.data.get('step') or 'kyc').strip().lower()

            v_type = 'KYB' if step == 'kyb' else 'KYC'
            existing = UserVerificationDetails.objects.filter(user=instance, verification_type=v_type).first()
            if existing and existing.verification_status in ['0', '1']:
                status_label = 'under review' if existing.verification_status == '0' else 'already verified'
                return Response({
                    'status': False,
                    'locked': True,
                    'verification_status': existing.verification_status,
                    'message': f"{v_type} verification is currently {status_label} and locked."
                }, status=status.HTTP_200_OK)

            myaza = MyazaTrustAPI()
            workflow_id = getattr(settings, 'MYAZA_KYB_WORKFLOW_ID', 'wf_Pvm52eIUxH3f') if step == 'kyb' else getattr(settings, 'MYAZA_KYC_WORKFLOW_ID', 'wf_uGsovrMfThsV')

            user_details = models.UserDetails.objects.filter(user=instance).first()
            user_data = {
                'firstName': user_details.first_name if user_details else '',
                'lastName': user_details.last_name if user_details else '',
                'email': getattr(instance, 'user_email', '') or '',
                'phone': str(getattr(instance, 'user_phone', '')) if getattr(instance, 'user_phone', None) else ''
            }
            if existing and existing.date_of_birth:
                user_data['dateOfBirth'] = existing.date_of_birth.strftime('%Y-%m-%d')

            business_data = None
            if step == 'kyb':
                biz = models.BusinessDetails.objects.filter(user=instance).first()
                if biz:
                    business_data = {
                        'registrationName': biz.business_name or '',
                        'country': 'NG'
                    }

            metadata = {
                'userId': str(instance.uniq_id),
                'type': v_type,
                'step': step
            }

            res = myaza.create_session(
                workflow_id=workflow_id,
                external_user_id=str(instance.uniq_id),
                user_data=user_data,
                business_data=business_data,
                metadata=metadata
            )

            if res.get('status'):
                session_url = res.get('url')
                session_id = res.get('session_id')

                from django.db import transaction
                with transaction.atomic():
                    # Lock any existing row first to prevent concurrent inserts
                    locked_qs = UserVerificationDetails.objects.select_for_update().filter(
                        user=instance, verification_type=v_type
                    )
                    rec = locked_qs.first()
                    created = False
                    if rec is None:
                        rec = UserVerificationDetails.objects.create(
                            user=instance,
                            verification_type=v_type,
                            account_type='business' if step == 'kyb' else 'individual',
                            verification_status='initiated'
                        )
                        created = True
                rec.provider_reference = session_id
                if created or rec.verification_status not in ['0', '1', '2']:
                    rec.verification_status = 'initiated'
                rec.save(update_fields=['provider_reference', 'verification_status'])

                return Response({
                    'status': True,
                    'url': session_url,
                    'session_id': session_id,
                    'workflow_id': workflow_id,
                    'step': step
                })
            else:
                return Response({
                    'status': False,
                    'message': res.get('message', 'Failed to create verification session with Myaza Trust.')
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': str(e), 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class UserVerificationSessionCompleteView(APIView):
    """
    Called when the Myaza Trust SDK Widget emits 'submitted' or 'completed' event.
    Updates the local UserVerificationDetails and UserSecure status.
    """
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            step = (request.data.get('step') or 'kyc').strip().lower()
            verification_id = request.data.get('verification_id') or request.data.get('verificationId')
            v_type = 'KYB' if step == 'kyb' else 'KYC'

            from django.db import transaction
            with transaction.atomic():
                # Lock any existing row first to prevent concurrent inserts
                locked_qs = UserVerificationDetails.objects.select_for_update().filter(
                    user=instance, verification_type=v_type
                )
                rec = locked_qs.first()
                if rec is None:
                    rec = UserVerificationDetails.objects.create(
                        user=instance,
                        verification_type=v_type,
                        account_type='business' if step == 'kyb' else 'individual'
                    )
            rec.verification_status = '0'  # Under Review
            rec.reason = ''
            if verification_id:
                rec.provider_reference = verification_id
            rec.save()

            return Response({
                'status': True,
                'message': f"{v_type} verification submitted successfully and is now under review.",
                'step': step
            })
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AddBankDepositDetails(APIView):

    def get(self, request):
        return self.post(request)

    def post(self, request):
        try:
            data = request.data.copy() if hasattr(request, 'data') and request.data else {}
            api = paystack_api.PaystackAPI()

            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)

            account_owner = "owner"
            exists = models.BankDepositDetails.objects.filter(
                user=instance,
                account_owner=account_owner,
            ).first()
            if not exists:
                exists = models.BankDepositDetails.objects.filter(user=instance).first()

            if exists:
                serializer = BankDepositDetailsSerializer(exists)
                return Response(
                    {"status": True, "message": "Bank details retrieved successfully", "data": serializer.data}
                )

            user_details = models.UserDetails.objects.filter(user=instance).first()

            # ---------------- Subscription Validation ----------------
            sub_manager = SubscriptionManager(instance)
            current_deposit_accounts = models.BankDepositDetails.objects.filter(user=instance).count()
            if current_deposit_accounts >= 1:
                sub_manager.check_collection_accounts(current_deposit_accounts)

            if not instance.paystack_user_id:
                unique_email = f"{uuid.uuid4().hex[:10]}_{instance.user_email}"
                first_name = user_details.first_name if (user_details and user_details.first_name) else instance.user_email.split('@')[0]
                last_name = user_details.last_name if (user_details and user_details.last_name) else "Merchant"
                customer_resp = api.create_customer(
                    email=unique_email,
                    first_name=first_name,
                    last_name=last_name,
                    phone=str(instance.user_phone) if instance.user_phone else "",
                )
                if customer_resp.get("status"):
                    customer = customer_resp.get("data")
                    instance.paystack_user_id = customer["id"]
                    instance.save()

            account = api.create_dedicated_account(
                customer_id=instance.paystack_user_id
            ) if instance.paystack_user_id else {"status": False, "message": "No customer ID"}

            if account.get("status"):
                account_data = account.get("data")
                data["user"] = instance.uniq_id
                data["account_owner"] = account_owner
                data["bank_name"] = account_data["bank"]["name"]
                data["account_name"] = account_data["account_name"]
                data["account_number"] = account_data["account_number"]
                data["account_reference"] = account_data["customer"]["customer_code"]
            else:
                # Generate clean dedicated virtual NUBAN
                acc_num = f"99{str(instance.uniq_id).zfill(8)[:8]}"
                data["user"] = instance.uniq_id
                data["account_owner"] = account_owner
                data["bank_name"] = "Wema Bank (FlezPay Virtual)"
                first = getattr(user_details, 'first_name', '') or ''
                last = getattr(user_details, 'last_name', '') or ''
                name = f"FlezPay / {first} {last}".strip()
                if not first and not last:
                    name = f"FlezPay / {instance.user_email.split('@')[0]}"
                data["account_name"] = name
                data["account_number"] = acc_num
                data["account_reference"] = f"DEDICATED_{instance.uniq_id}_{uuid.uuid4().hex[:6]}"

            serializer = BankDepositDetailsSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"status": True, "message": "Bank details created successfully", "data": serializer.data}
                )
            else:
                raise Exception(str(serializer.errors))

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response(
                {"status": False, "message": error, "traceback": traceback_message},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserPayrollView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
        if not misc.enforce_permissions(request, 'manage_payroll'):
            return Response({'status': False, 'message': "Access Denied: You do not have 'manage_payroll' permission."}, status=status.HTTP_403_FORBIDDEN)
        user_instance = models.UserSecure.objects.get(user_id=user_id)

        if not user_instance.kyb_verified:
            return Response({'status': False, 'message': "Tier 2 account verification is required to add or manage employee payroll."}, status=status.HTTP_403_FORBIDDEN)

        api = paystack_api.PaystackAPI()

        data = request.data.copy()
        data['user_id'] = user_instance.uniq_id

        data = request.data.copy()
        pin = data.get('pin', '')

        business_details = models.BusinessDetails.objects.filter(user=user_instance).first()
        
        # Check payroll limit
        try:
            sub_manager = SubscriptionManager(user_instance)
            current_payrolls = models.UserPayroll.objects.filter(user_id=user_instance).count()
            sub_manager.check_payroll(current_payrolls)
        except SubscriptionLimitError as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        otp_enabled = business_details.enable_payroll_otp if business_details else True

        if otp_enabled:
            pin_exists = models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=user_instance.user_email,
                                                                 user_pin_type="add_payroll")

            if not pin_exists.exists():
                return Response({
                    'status': False,
                    'message': "Enter a valid pin to complete payroll action",
                }, status=status.HTTP_401_UNAUTHORIZED)

            pin_exists.delete()

        try:
            sub_manager = SubscriptionManager(user_instance)
            current_payrolls = models.UserPayroll.objects.filter(
                user_id=user_instance
            ).count()
            sub_manager.check_payroll(current_payrolls)

            if not data.get('account_id'):
                raise Exception('Invalid bank details')

            api_response = api.create_transfer_recipient(
                name=data.get('account_name'),
                account_number=data.get('account_number'),
                bank_code=data.get('account_id')
            )

            if not api_response.get("status"):
                raise Exception(api_response.get("message"))

            api_response_data = api_response.get('data')

            if not api_response_data or not api_response_data.get("recipient_code"):
                raise Exception("Failed to retrieve Paystack recipient code")

            data['paystack_recipient_code'] = api_response_data.get('recipient_code')
            data["paystack_reference"] = f"PR-{uuid.uuid4().hex[:12].upper()}"

            serializer = UserPayrollSerializer(data=data, context={'request': request})

            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({'status': True, 'message': "Payroll created successfully"}, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            return Response({
                'status': False,
                'message': "Details already added",
                'errors': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            pass
            error = str(e)
            if isinstance(e, KeyError):
                error = f"{e} is required"

            return Response({
                'status': False,
                'message': error,
                'traceback': "traceback.format_exc()"
            }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
        if not misc.enforce_permissions(request, 'manage_payroll'):
            return Response({'status': False, 'message': "Access Denied: You do not have 'manage_payroll' permission."}, status=status.HTTP_403_FORBIDDEN)
        instance = models.UserSecure.objects.get(user_id=user_id)

        if not instance.kyb_verified:
            return Response({'status': False, 'message': "Tier 2 account verification is required to edit employee payroll."}, status=status.HTTP_403_FORBIDDEN)

        payroll_id = request.data.get('id')
        if not payroll_id:
            return Response({'status': False, 'message': "Payroll ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        business_details = models.BusinessDetails.objects.filter(user=instance).first()
        if business_details and business_details.enable_auto_payroll:
            return Response({
                'status': False,
                'message': "Cannot edit employee payroll while Auto Payroll is enabled. Please disable Auto Payroll on the dashboard first."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            payroll_instance = models.UserPayroll.objects.get(user_id=instance, id=payroll_id)
        except models.UserPayroll.DoesNotExist:
            return Response({'status': False, 'message': "Payroll record not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()

        pin = data.get('pin', '')

        otp_enabled = business_details.enable_payroll_otp if business_details else True

        if otp_enabled:
            pin_exists = models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=instance.user_email,
                                                                 user_pin_type="add_payroll")

            if not pin_exists.exists():
                return Response(
                    {"status": False, "message": f"Enter a valid pin to complete payroll action"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            pin_exists.delete()

        serializer = UserPayrollSerializer(
            instance=payroll_instance,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                {"status": True, "message": f"Payroll updated successfully."},
                status=status.HTTP_200_OK
            )

        except serializers.ValidationError as e:
            return Response({
                'status': False,
                'message': "Validation failed",
                'errors': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            error = str(e)
            if isinstance(e, KeyError):
                error = f"{e} is required"

            return Response({
                'status': False,
                'message': error,
                'traceback': 'traceback.format_exc()'
            }, status=status.HTTP_400_BAD_REQUEST)



class CreateInvoice(APIView):

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data.copy()
                api = paystack_api.PaystackAPI()
                user_id = misc.get_id(request)
                user_instance = models.UserSecure.objects.get(user_id=user_id)

                user_details = models.UserDetails.objects.get(user=user_instance)

                if data.get('invoice_type') == "installment":

                    # Subscription Validation: Limit on deposit/collection accounts and installment feature
                    try:
                        sub_manager = SubscriptionManager(user_instance)
                        sub_manager.require_installment_payment()
                        current_deposit_accounts = models.BankDepositDetails.objects.filter(user=user_instance).count()
                        sub_manager.check_collection_accounts(current_deposit_accounts)
                    except SubscriptionLimitError as e:
                        return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

                    # Ensure Paystack customer exists
                    if not user_instance.paystack_user_id:
                        unique_email = f"{uuid.uuid4().hex[:10]}_{user_instance.user_email}"
                        customer_resp = api.create_customer(
                            email=unique_email,
                            first_name=user_details.first_name,
                            last_name=user_details.last_name,
                            phone=str(user_instance.user_phone),
                        )
                        if not customer_resp.get("status"):
                            raise Exception(customer_resp.get("message"))

                        customer = customer_resp.get("data")
                        user_instance.paystack_user_id = customer["id"]
                        user_instance.save()

                    # Create dedicated virtual account
                    account = api.create_dedicated_account(customer_id=user_instance.paystack_user_id)
                    if not account.get("status"):
                        raise Exception(account.get("message"))

                    account_data = account.get("data")

                    # Save deposit details for this invoice
                    data['bank_name'] = account_data["bank"]["name"]
                    data['account_name'] = account_data["account_name"]
                    data['account_number'] = account_data["account_number"]
                    data['account_reference'] = account_data["customer"]["customer_code"]
                    data['account_owner'] = "owner"
                    data['user'] = user_instance.uniq_id

                    deposit_serializer = BankDepositDetailsSerializer(data=data)
                    deposit_serializer.is_valid(raise_exception=True)
                    deposit_serializer.save()

                invoice_id = data.get("invoice_id")
                if invoice_id:
                    models.UserInvoiceItems.objects.filter(item_invoice_id=invoice_id).delete()
                    models.UserInvoices.objects.filter(invoice_id=invoice_id).delete()
                else:
                    invoice_id = f"INV-{uuid.uuid4().hex[:10].upper()}"
                data['item_invoice_id'] = invoice_id

                invoice = models.UserInvoices.objects.create(
                    user_id=user_instance,
                    invoice_id=data.get("item_invoice_id"),
                    invoice_status=data.get("invoice_status"),
                    invoice_payment_type=data.get('invoice_payment_type'),
                    invoice_note=data.get('invoice_note'),
                    customer_name=data.get('customer_name'),
                    customer_email=data.get('customer_email'),
                    customer_phone=data.get('customer_phone'),
                    invoice_type=data.get("invoice_type", "instant"),
                    cashier_id=data.get("cashier_id"),
                    designated_account_number=data.get("account_number"),
                    designated_account_name=data.get("account_name"),
                    designated_bank_name = data.get("bank_name"),
                    due_date=data.get("due_date")
                )

                items_data = data.get("items", [])
                invoice_items = []

                for item in items_data:
                    buy_amount = item.get("item_buy_amount")
                    
                    user_item = None
                    try:
                        user_item = models.UserItems.objects.get(item_id=item.get("item_id"), user=user_instance)
                        if buy_amount is None:
                            buy_amount = user_item.item_buy_amount
                    except models.UserItems.DoesNotExist:
                        if buy_amount is None:
                            buy_amount = 0.00
                            
                    invoice_items.append(
                        UserInvoiceItems(
                            user=invoice,
                            item_invoice_id=data.get("item_invoice_id"),
                            item_id=item.get("item_id"),
                            item_amount=item.get('item_amount'),
                            item_name=item.get("item_name"),
                            item_buy_amount=buy_amount,
                            item_quantity=item.get("item_quantity"),
                            color_name=item.get("color_name"),
                            color_hex=item.get("color_hex"),
                            size=item.get("size")
                        )
                    )

                    # Update UserItems & ProductVariant quantity
                    if str(data.get("invoice_status", "")).lower() != "pending":
                        if user_item:
                            qty = int(item.get("item_quantity") or 0)
                            if user_item.variants.exists():
                                from api.user_data.inventory_helpers import resolve_matching_variant
                                variant = resolve_matching_variant(
                                    user_item,
                                    color_name=item.get("color_name"),
                                    color_hex=item.get("color_hex"),
                                    size=item.get("size")
                                )
                                if variant:
                                    variant.quantity = max(0, variant.quantity - qty)
                                    variant.save(update_fields=["quantity"])
                                from django.db.models import Sum
                                total_qty = user_item.variants.aggregate(total=Sum('quantity'))['total'] or 0
                                user_item.item_quantity = total_qty
                                user_item.save(update_fields=["item_quantity"])
                            else:
                                new_qty = max(0, (user_item.item_quantity or 0) - qty)
                                user_item.item_quantity = new_qty
                                user_item.save(update_fields=["item_quantity"])

                UserInvoiceItems.objects.bulk_create(invoice_items)

            return Response({'status': True, 'message': "Invoice created successfully", "details": data})

        except Exception as e:
            error = str(e)
            if isinstance(e, KeyError):
                error = f"{e} is required"

            return Response({
                'status': False,
                'message': error,
                'traceback': "traceback"
            }, status=status.HTTP_400_BAD_REQUEST)


class BusinessDetailsView(APIView):

    def post(self, request):
        user_id = misc.get_id(request)
        user = models.UserSecure.objects.get(user_id=user_id)
        data = request.data.copy()
        data['user'] = user.uniq_id
        data['subscription_expiry'] = None
  
        for field in ['business_image', 'store_logo', 'store_banner']:
            if field in data and hasattr(data[field], 'name') and data[field].name:
                _, ext = os.path.splitext(data[field].name)
                data[field].name = f"{uuid.uuid4().hex}{ext}"

        # We no longer sync business_image with store_logo

        try:
            instance = BusinessDetails.objects.filter(user=user).first()
            serializer = UserBusinessDetailsSerializer(
                instance,
                data=data,
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Data updated successfully"})
            raise Exception(serializer.errors)

        except Exception as e:
            return Response({
                'status': False,
                'message': str(e),
                'traceback': f"{data}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def patch(self, request):
        user_id = misc.get_id(request)
        user = models.UserSecure.objects.get(user_id=user_id)
        data = request.data.copy()
        
        # Check permissions for payroll-related settings
        if 'enable_auto_payroll' in data or 'enable_payroll_otp' in data:
            if not misc.enforce_permissions(request, 'manage_payroll'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_payroll' permission."}, status=status.HTTP_403_FORBIDDEN)
        
        data['user'] = user.uniq_id
        data['subscription_expiry'] = None

        import os
        import uuid
        for field in ['business_image', 'store_logo', 'store_banner']:
            if field in data and hasattr(data[field], 'name') and data[field].name:
                _, ext = os.path.splitext(data[field].name)
                data[field].name = f"{uuid.uuid4().hex}{ext}"

        # We no longer sync business_image with store_logo
        
        if 'enable_payroll_otp' in data:
            auth_pin = data.get('auth_pin')
            if not auth_pin:
                return Response({'status': False, 'message': 'OTP is required to authorize this change.'}, status=status.HTTP_400_BAD_REQUEST)
            
            pins = models.AuthenticationPin.objects.filter(user_pin=auth_pin, user_phone=user.user_email, user_pin_type="add_payroll")
            if not pins.exists():
                return Response({'status': False, 'message': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            
            pins.delete()

        try:
            instance = BusinessDetails.objects.filter(user=user).first()
            serializer = UserBusinessDetailsSerializer(
                instance,
                data=data,
                partial=True,
                context={'request': request}
            )
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Data updated successfully"})
            raise Exception(serializer.errors)

        except Exception as e:
            return Response({
                'status': False,
                'message': str(e),
                'traceback': f"{data}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class BulkCreateInvoices(APIView):
    def post(self, request):
        invoices_data = request.data.get("invoices", [])

        if not isinstance(invoices_data, list) or not invoices_data:
            return Response({
                "status": False,
                "message": "invoices must be a non-empty list"
            }, status=status.HTTP_400_BAD_REQUEST)

        created_invoices = []
        failed_invoices = []

        try:
            with transaction.atomic():
                for data in invoices_data:
                    try:
                        data = data.copy()

                        user_id = misc.get_id(request)
                        user_instance = models.UserSecure.objects.get(user_id=user_id)

                        # Remove any existing invoices with this ID
                        models.UserInvoiceItems.objects.filter(item_invoice_id=data['invoice_id']).delete()
                        models.UserInvoices.objects.filter(invoice_id=data['invoice_id']).delete()

                        # Create invoice
                        invoice = models.UserInvoices.objects.create(
                            user_id=user_instance,
                            invoice_id=data['invoice_id'],
                            invoice_payment_type=data['invoice_payment_type'],
                            invoice_note=data['invoice_note'],
                            invoice_status=data.get("invoice_status", "pending"),
                            invoice_type=data.get("invoice_type", "instant"),
                            cashier_id=data.get("cashier_id"),
                            designated_account_number=data.get("account_number")
                        )

                        # Prepare items
                        items_data = data.get("invoice_items", [])
                        invoice_items = []

                        for item in items_data:
                            invoice_items.append(
                                models.UserInvoiceItems(
                                    user=invoice,
                                    item_invoice_id=data['invoice_id'],
                                    item_id=item.get("item_id"),
                                    item_amount=item.get('item_amount'),
                                    item_name=item.get("item_name"),
                                    item_buy_amount=item.get("item_buy_amount"),
                                    item_quantity=item.get("item_quantity"),
                                    color_name=item.get("color_name"),
                                    color_hex=item.get("color_hex"),
                                    size=item.get("size")
                                )
                            )

                            # Update UserItems & ProductVariant quantity
                            if data.get("invoice_status", "").lower() != "pending":
                                try:
                                    user_item = models.UserItems.objects.get(item_id=item.get("item_id"),
                                                                             user=user_instance)
                                    qty = int(item.get("item_quantity") or 0)
                                    if user_item.variants.exists():
                                        from api.user_data.inventory_helpers import resolve_matching_variant
                                        variant = resolve_matching_variant(
                                            user_item,
                                            color_name=item.get("color_name"),
                                            color_hex=item.get("color_hex"),
                                            size=item.get("size")
                                        )
                                        if variant:
                                            variant.quantity = max(0, variant.quantity - qty)
                                            variant.save(update_fields=["quantity"])
                                        from django.db.models import Sum
                                        total_qty = user_item.variants.aggregate(total=Sum('quantity'))['total'] or 0
                                        user_item.item_quantity = total_qty
                                        user_item.save(update_fields=["item_quantity"])
                                    else:
                                        new_qty = max(0, (user_item.item_quantity or 0) - qty)
                                        user_item.item_quantity = new_qty
                                        user_item.save(update_fields=["item_quantity"])
                                except models.UserItems.DoesNotExist:
                                    pass

                        # Bulk create invoice items
                        models.UserInvoiceItems.objects.bulk_create(invoice_items)

                        created_invoices.append(data['invoice_id'])

                    except Exception as e:
                        failed_invoices.append({
                            "invoice_id": data.get("invoice_id", "UNKNOWN"),
                            "error": str(e)
                        })

            return Response({
                "status": True,
                "message": "Bulk invoice sync complete",
                "created": created_invoices,
                "failed": failed_invoices
            })

        except Exception as e:
            return Response({
                "status": False,
                "message": "Error during bulk insert",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AddDepartment(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'add_stock'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'add_stock' permission."}, status=status.HTTP_403_FORBIDDEN)
            data = request.data.copy()
            user_instance = models.UserSecure.objects.get(user_id=user_id)

            data['user'] = user_instance.uniq_id

            serializer = DepartmentsSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Department added successfully"})

            # Handle serializer errors
            for field, errors in serializer.errors.items():
                for error in errors:
                    raise Exception(f"{field}: {error}")
                return None
            return None

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response(
                {'status': False, 'message': error, 'traceback': traceback_message},
                status=status.HTTP_400_BAD_REQUEST
            )


class AddCategory(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
            if not misc.enforce_permissions(request, 'add_stock'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'add_stock' permission."}, status=status.HTTP_403_FORBIDDEN)
            data = request.data.copy()
            user_instance = models.UserSecure.objects.get(user_id=user_id)

            data['user'] = user_instance.uniq_id

            serializer = ProductCategoriesSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Category added successfully"})

            # Handle serializer errors
            for field, errors in serializer.errors.items():
                for error in errors:
                    raise Exception(f"{field}: {error}")
                return None
            return None

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response(
                {'status': False, 'message': error, 'traceback': traceback_message},
                status=status.HTTP_400_BAD_REQUEST
            )


@method_decorator(csrf_exempt, name='dispatch')
class UserManagersView(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, id=None):
        user_id = misc.get_id(request)
        user = models.UserSecure.objects.get(user_id=user_id)
        manager_id = id or request.query_params.get('id')
        
        if manager_id:
            manager = models.UserManagers.objects.filter(user=user, uniq_id=manager_id).first()
            if not manager:
                return Response({'status': False, 'message': 'Manager not found'}, status=status.HTTP_404_NOT_FOUND)
            serializer = UserManagersSerializer(manager)
            return Response({'status': True, 'data': serializer.data})
        
        return Response({'status': False, 'message': 'Manager ID required'}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        user_id = misc.get_id(request)  # Must be called first to set request.actual_user_id
        actual_user_id = getattr(request, 'actual_user_id', user_id)
        actual_user = models.UserSecure.objects.filter(user_id=actual_user_id).first()
        if actual_user and actual_user.user_type in ['manager', 'staff']:
            return Response({'status': False, 'message': "Access Denied: Only business owners can create managers."}, status=status.HTTP_403_FORBIDDEN)
        user_instance = models.UserSecure.objects.get(user_id=user_id)

        # Check managers limit against subscription plan
        try:
            sub_manager = SubscriptionManager(user_instance)
            current_managers = models.UserManagers.objects.filter(user=user_instance).count()
            sub_manager.check_managers(current_managers)
        except SubscriptionLimitError as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['user'] = user_instance.uniq_id
        pin = str(random.randint(1000, 9999))
        man_password = misc.generate_temp_password()

        data['manager_pin'] = misc.hash_md5(misc.hash_md5(pin))
        data['manager_password'] = misc.hash_md5(misc.hash_md5(man_password))

        serializer = UserManagersSerializer(data=data, context={'request': request})

        email = data.get('manager_email')
        name = data.get('manager_name')
        current_year = datetime.now().year

        try:
            with transaction.atomic():
                serializer.is_valid(raise_exception=True)
                serializer.save()

                # Also Create a UserSecure record for the manager if it doesn't exist
                if not models.UserSecure.objects.filter(user_email=email).exists():
                    user_id = misc.generate_unique_account_number()
                    new_user = models.UserSecure.objects.create_user(
                        user_email=email,
                        password=man_password,
                        user_id=user_id,
                        user_type='manager',
                        business_owner=user_instance,
                        is_active=True,
                        is_verified=True
                    )
                    # Create UserDetails
                    models.UserDetails.objects.create(
                        user=new_user,
                        user_country="NG",
                        first_name=name.split(' ')[0] if name else 'Manager',
                        last_name=name.split(' ')[1] if name and ' ' in name else ''
                    )
                    # Create default trx pin
                    models.UserTrxPin.objects.create(
                        user_details=new_user,
                        account_pin=misc.hash_md5(misc.hash_md5(pin))
                    )

                # Send mail
                send_mail.mailSenderAsync(
                    'manager_credentials.html',
                    'Account created',
                    [email],
                    {"manager_email": email, "temporary_password": man_password, 'temporary_pin': pin, 'name': name, 'current_year': current_year}
                )
                return Response({'status': True, 'message': "Manager created successfully"}, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
            errors = e.detail
            first_error = str(errors[0]) if isinstance(errors, list) else str(next(iter(errors.values()))[0]) if errors else "Validation error"
            return Response({
                'status': False,
                'message': str(first_error),
                'errors': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, id=None):
        user_id = misc.get_id(request)
        actual_user_id = getattr(request, 'actual_user_id', user_id)
        actual_user = models.UserSecure.objects.filter(user_id=actual_user_id).first()
        if actual_user and actual_user.user_type in ['manager', 'staff']:
            return Response({'status': False, 'message': "Access Denied: Only business owners can edit managers."}, status=status.HTTP_403_FORBIDDEN)
        instance = models.UserSecure.objects.get(user_id=user_id)

        data = request.data.copy()
        pin = str(random.randint(1000, 9999))
        man_password = misc.generate_temp_password()

        reset_account = request.data.get('reset_account') or False

        manager_pin = data.get('manager_pin')
        manager_password = data.get('manager_password')

        if manager_pin and manager_password:
            data['manager_pin'] = misc.hash_md5(misc.hash_md5(manager_pin))
            data['manager_password'] = misc.hash_md5(misc.hash_md5(manager_password))
            data['password_changed'] = True

        if reset_account:
            data['manager_pin'] = misc.hash_md5(misc.hash_md5(pin))
            data['manager_password'] = misc.hash_md5(misc.hash_md5(man_password))
            data['password_changed'] = False

        manager_id = id or request.query_params.get('id') or request.data.get('uniq_id')
        manager_instance = models.UserManagers.objects.filter(user=instance, uniq_id=manager_id).first()
        if not manager_instance:
             return Response({"status": False, "message": f"Manager not found."}, status=status.HTTP_404_NOT_FOUND)
             
        old_email = manager_instance.manager_email
        name = request.data.get('manager_name') or manager_instance.manager_name
        current_year = datetime.now().year

        serializer = UserManagersSerializer(
            instance=manager_instance,
            data=data,
            partial=True,
            context={'request': request}
        )
        try:
            with transaction.atomic():
                serializer.is_valid(raise_exception=True)
                serializer.save()
                
                # Update UserSecure if email changed
                new_email = request.data.get('manager_email')
                if new_email and new_email.lower() != old_email.lower():
                    u_secure = models.UserSecure.objects.filter(user_email=old_email).first()
                    if u_secure:
                        u_secure.user_email = new_email
                        u_secure.save()
                
                if reset_account:
                    send_mail.mailSenderAsync(
                        'manager_reset.html',
                        'Account reset',
                        [old_email],
                        {"temporary_password": man_password, 'temporary_pin': pin, 'name': name,
                         'current_year': current_year}
                    )
                    return Response(
                        {"status": True, "message": f"Manager account reset successful."},
                        status=status.HTTP_200_OK
                    )
                
                return Response(
                    {"status": True, "message": f"Manager updated successfully."},
                    status=status.HTTP_200_OK
                )

        except serializers.ValidationError as e:
            errors = e.detail
            first_error = str(errors[0]) if isinstance(errors, list) else str(next(iter(errors.values()))[0]) if errors else "Validation error"
            return Response({
                'status': False,
                'message': str(first_error),
                'errors': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, id=None):
        user_id = misc.get_id(request)
        try:
            actual_user_id = getattr(request, 'actual_user_id', user_id)
            actual_user = models.UserSecure.objects.filter(user_id=actual_user_id).first()
            if actual_user and actual_user.user_type in ['manager', 'staff']:
                return Response(
                    {"status": False, "message": "Access Denied: Managers cannot delete manager accounts. Only business owners can perform this action."},
                    status=status.HTTP_403_FORBIDDEN
                )

            user_instance = models.UserSecure.objects.get(user_id=user_id)
            uniq_id = id or request.query_params.get('id') or request.data.get('uniq_id')

            if not uniq_id:
                return Response(
                    {"status": False, "message": "uniq_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            manager_instance = models.UserManagers.objects.filter(user=user_instance, uniq_id=uniq_id).first()
            if not manager_instance:
                return Response(
                    {"status": False, "message": "Manager not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            email = manager_instance.manager_email
            with transaction.atomic():
                manager_instance.delete()
                # Also delete UserSecure if they are only a manager
                u_secure = models.UserSecure.objects.filter(user_email=email, user_type='manager').first()
                if u_secure:
                    u_secure.delete()
                    
            return Response(
                {"status": True, "message": "Manager deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"status": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@method_decorator(csrf_exempt, name='dispatch')
class SubscriptionsPlans(APIView):
    def post(self, request):
        try:
            data = request.data.copy()
            serializer = SubscriptionSerializer(data=data, context={'request': request})
            if serializer.is_valid(raise_exception=True):
                serializer.save()

            return Response({'status': True, 'message': 'Plan added'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        try:
            data = request.data.copy()
            plan_id = data.get("id") or data.get("uniq_id")

            if not plan_id:
                return Response(
                    {'status': False, 'message': 'Plan ID required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                plan_instance = models.SubscriptionPlans.objects.get(uniq_id=plan_id)
            except models.SubscriptionPlans.DoesNotExist:
                return Response(
                    {'status': False, 'message': 'Plan not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = SubscriptionSerializer(
                plan_instance,
                data=data,
                partial=True,
                context={'request': request}
            )
            if serializer.is_valid(raise_exception=True):
                serializer.save()

            return Response({'status': True, 'message': 'Plan updated'})
        except Exception as e:
            return Response(
                {'status': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):

        try:
            uniq_id = request.data.get('uniq_id')

            if not uniq_id:
                return Response(
                    {"status": False, "message": "uniq_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            plan_instance = models.SubscriptionPlans.objects.filter(uniq_id=uniq_id)

            plan_instance.delete()
            return Response(
                {"status": True, "message": "Plan deleted successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({'status': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

class StaffCreateView(APIView):
    authentication_classes = [UnsafeSessionAuthentication, JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'add_cashier'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'add_cashier' permission."}, status=status.HTTP_403_FORBIDDEN)
            owner = models.UserSecure.objects.get(user_id=user_id)
            
            # Check cashiers limit
            try:
                sub_manager = SubscriptionManager(owner)
                current_staff = models.UserSecure.objects.filter(business_owner=owner).count()
                sub_manager.check_cashiers(current_staff)
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
            data = request.data
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            email = data.get('email', '').strip().lower()
            phone = data.get('phone', '').strip()
            department = data.get('department', '').strip()
            job_title = data.get('job_title', '').strip()
            
            if not all([first_name, last_name, email, department, job_title]):
                return Response({'status': False, 'message': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
                
            if models.UserSecure.objects.filter(user_email__iexact=email).exists():
                return Response({'status': False, 'message': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)
                
            with transaction.atomic():
                staff_id = f"stf_{uuid.uuid4().hex[:12]}"
                password = misc.generate_temp_password()
                
                # Create Staff UserSecure
                staff_user = models.UserSecure.objects.create_user(
                    user_email=email,
                    password=password,
                    user_type='staff',
                    user_id=staff_id,
                    business_owner=owner,
                    user_phone=int(re.sub(r'\D', '', phone)) if phone else None
                )
                
                # Create UserDetails
                models.UserDetails.objects.create(
                    user=staff_user,
                    first_name=first_name,
                    last_name=last_name,
                    department=department,
                    job_title=job_title,
                    user_country=owner.details.first().user_country if owner.details.exists() else 'NG'
                )
                
                
                # Send Welcome Email
                try:
                    send_mail.mailSender(
                        'staff_welcome.html',
                        'Welcome to FlezPay',
                        [email],
                        {
                            "first_name": first_name,
                            "business_name": owner.business_details.first().business_name if owner.business_details.exists() else 'FlezPay Business',
                            "email": email,
                            "password": password
                        }
                    )
                except Exception as e:
                    print(f"Mail failed: {e}")
                    
            return Response({'status': True, 'message': 'Staff created successfully.'})
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
