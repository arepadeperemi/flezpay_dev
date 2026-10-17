import traceback
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from api import models
from api.functions import misc, send_mail
from decimal import Decimal
import uuid
from api.external.paystack_api import PaystackAPI

class RunPayrollView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_payroll'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_payroll' permission."}, status=status.HTTP_403_FORBIDDEN)
            user_instance = models.UserSecure.objects.get(user_id=user_id)

            # Check if withdrawals are disabled for acting user (e.g., staff/manager) or account owner
            actual_user_id = getattr(request, 'actual_user_id', None)
            if actual_user_id:
                actual_user = models.UserSecure.objects.filter(user_id=actual_user_id).first()
                if actual_user and actual_user.withdrawals_disabled:
                    return Response({
                        'status': False,
                        'message': 'Withdrawals have been temporarily disabled for your account. Please contact support for assistance.'
                    }, status=status.HTTP_403_FORBIDDEN)

            if user_instance.withdrawals_disabled:
                return Response({
                    'status': False,
                    'message': 'Withdrawals have been temporarily disabled for your account. Please contact support for assistance.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            if not user_instance.kyb_verified:
                return Response({
                    'status': False,
                    'message': 'Tier 2 account verification is required to disburse payroll. Please complete verification first.'
                }, status=status.HTTP_403_FORBIDDEN)

            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(user_instance).require_payroll()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
            user_details = models.UserDetails.objects.filter(user=user_instance).first()
            if not user_details or user_details.user_country != 'NG':
                return Response({'status': False, 'message': 'Payroll processing is currently only supported for businesses in Nigeria.'}, status=status.HTTP_400_BAD_REQUEST)
            
            pin = request.data.get('pin', '')
            
            business_details = models.BusinessDetails.objects.filter(user=user_instance).first()
            otp_enabled = business_details.enable_payroll_otp if business_details else True
            
            if otp_enabled:
                # For simplicity, we use the same add_payroll pin type for run_payroll too
                pin_exists = models.AuthenticationPin.objects.filter(
                    user_pin=pin, 
                    user_phone=user_instance.user_email,
                    user_pin_type="add_payroll"
                )
    
                if not pin_exists.exists():
                    return Response({
                        'status': False,
                        'message': "Enter a valid pin to complete payroll action",
                    }, status=status.HTTP_401_UNAUTHORIZED)
    
                pin_exists.delete()

            # Fetch active (Ready) employees
            active_payrolls = models.UserPayroll.objects.filter(
                user_id=user_instance,
                pay_status='active'
            )

            if not active_payrolls.exists():
                return Response({'status': False, 'message': 'No active employees found to process.'}, status=status.HTTP_400_BAD_REQUEST)

            transfers_payload = []
            valid_payrolls_data = []
            
            from api.user_data.data_views import calculate_total_balance
            available_balance = calculate_total_balance(user_instance)
            overdraft_limit = float(business_details.payroll_overdraft) if business_details else 0.0
            
            cumulative_deductions = 0.0
            total_processed = 0
            count = 0
            insufficient_funds = False
            paystack_error = False
            
            from datetime import datetime
            now = datetime.now()
            current_day = now.day
            
            paystack = PaystackAPI()
            
            for payroll in active_payrolls:
                # Disbursement date check
                pay_date_str = payroll.get_pay_date()
                if not pay_date_str:
                    continue
                    
                try:
                    pay_date_obj = datetime.strptime(pay_date_str, "%Y-%m-%d")
                except ValueError:
                    continue
                    
                freq = payroll.get_pay_frequency() or 'monthly'
                is_due = False
                
                if freq == 'daily':
                    is_due = pay_date_obj.date() <= now.date()
                elif freq == 'weekly':
                    is_due = pay_date_obj.date() <= now.date()
                elif freq == 'quarterly':
                    is_due = pay_date_obj.date() <= now.date()
                elif freq == 'annually':
                    is_due = pay_date_obj.date() <= now.date()
                else: # monthly
                    is_due = pay_date_obj.day <= current_day
                    
                if not is_due:
                    continue
                    
                from datetime import timedelta
                query_kwargs = {
                    'user': user_instance,
                    'trx_source': 'Payroll',
                    'user_collection_id': payroll.account_number,
                    'trx_status__in': ['completed', 'pending']
                }
                
                if freq == 'daily':
                    query_kwargs['timestamp__date'] = now.date()
                elif freq == 'weekly':
                    query_kwargs['timestamp__gte'] = now - timedelta(days=6)
                elif freq == 'quarterly':
                    quarter = (now.month - 1) // 3 + 1
                    query_kwargs['timestamp__year'] = now.year
                    query_kwargs['timestamp__month__gte'] = (quarter - 1) * 3 + 1
                    query_kwargs['timestamp__month__lte'] = quarter * 3
                elif freq == 'annually':
                    query_kwargs['timestamp__year'] = now.year
                else: # monthly
                    query_kwargs['timestamp__month'] = now.month
                    query_kwargs['timestamp__year'] = now.year
                    
                already_paid = models.UserTransactions.objects.filter(**query_kwargs).exists()
                
                if already_paid:
                    continue
                    
                amount = payroll.get_pay_amount() + payroll.get_allowances() - payroll.get_deductions()
                
                if amount <= 0:
                    continue
                    
                if not payroll.paystack_recipient_code:
                    rcp_resp = paystack.create_transfer_recipient(
                        name=payroll.account_name,
                        account_number=payroll.account_number,
                        bank_code=payroll.account_id
                    )
                    if rcp_resp.get("status"):
                        payroll.paystack_recipient_code = rcp_resp.get("data", {}).get("recipient_code")
                        payroll.save(update_fields=['paystack_recipient_code'])
                        
                if not payroll.paystack_recipient_code:
                    continue
                    
                total_required = float(amount) + cumulative_deductions
                if total_required > (available_balance + overdraft_limit):
                    insufficient_funds = True
                    continue
                    
                cumulative_deductions += float(amount)
                    
                reference = f"PR-{uuid.uuid4().hex[:12].upper()}"
                
                transfers_payload.append({
                    "amount": int(amount * 100),
                    "recipient": payroll.paystack_recipient_code,
                    "reference": reference,
                    "reason": f"Payroll Disbursement: {payroll.account_name}"
                })
                
                valid_payrolls_data.append({
                    "payroll": payroll,
                    "amount": amount,
                    "reference": reference
                })

            if not transfers_payload:
                if insufficient_funds:
                    return Response({'status': False, 'message': 'Insufficient funds to process any payroll.'}, status=status.HTTP_400_BAD_REQUEST)
                return Response({'status': False, 'message': 'No eligible employees found. They may have already been paid this month, or their disbursement date has not arrived yet.'}, status=status.HTTP_400_BAD_REQUEST)

            paystack = PaystackAPI()
            chunk_size = 100
            
            for i in range(0, len(transfers_payload), chunk_size):
                payload_chunk = transfers_payload[i:i + chunk_size]
                data_chunk = valid_payrolls_data[i:i + chunk_size]
                
                try:
                    bulk_resp = paystack.bulk_transfer(payload_chunk)
                    
                    if not bulk_resp.get("status") and bulk_resp.get("meta", {}).get("invalidRecipients"):
                        invalid_recipients = bulk_resp.get("meta").get("invalidRecipients")
                        for item in data_chunk:
                            p = item["payroll"]
                            if p.paystack_recipient_code in invalid_recipients:
                                rcp_resp = paystack.create_transfer_recipient(
                                    name=p.account_name,
                                    account_number=p.account_number,
                                    bank_code=p.account_id
                                )
                                if rcp_resp.get("status"):
                                    new_rcp = rcp_resp.get("data", {}).get("recipient_code")
                                    p.paystack_recipient_code = new_rcp
                                    p.save(update_fields=['paystack_recipient_code'])
                                    for p_item in payload_chunk:
                                        if p_item["reference"] == item["reference"]:
                                            p_item["recipient"] = new_rcp
                        
                        bulk_resp = paystack.bulk_transfer(payload_chunk)
                    
                    if bulk_resp.get("status") is True:
                        transactions_to_create = []
                        for item in data_chunk:
                            p = item["payroll"]
                            transactions_to_create.append(
                                models.UserTransactions(
                                    user=user_instance,
                                    trx_amount=Decimal(str(item["amount"])),
                                    trx_currency='NGN',
                                    trx_type='payment',
                                    trx_status='pending',
                                    description=item["reference"],
                                    user_collection_id=p.account_number,
                                    destination_id=p.bank_name or '0',
                                    trx_source='Payroll'
                                )
                            )
                            total_processed += item["amount"]
                            count += 1
                        models.UserTransactions.objects.bulk_create(transactions_to_create)
                    else:
                        error_msg = bulk_resp.get('message', 'Unknown error')
                        meta = bulk_resp.get('meta', {})
                        if meta:
                            invalid_recipients = meta.get('invalidRecipients', [])
                            if invalid_recipients:
                                failed_names = []
                                for item in data_chunk:
                                    if item['payroll'].paystack_recipient_code in invalid_recipients:
                                        failed_names.append(item['payroll'].account_name)
                                if failed_names:
                                    error_msg += f". Invalid employees: {', '.join(failed_names)}"
                                    
                        try:
                            settings_obj = models.SiteSettings.objects.first()
                            admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
                            send_mail(
                                subject="Paystack Bulk Transfer Error",
                                message=f"An error occurred during manual payroll bulk transfer.\n\nAPI Response:\n{error_msg}",
                                from_email="no-reply@flezpay.com",
                                recipient_list=[admin_email],
                                fail_silently=True,
                            )
                        except Exception:
                            pass
                        paystack_error = error_msg
                except Exception as e:
                    paystack_error = "An unexpected exception occurred with the payment provider."
                    try:
                        settings_obj = models.SiteSettings.objects.first()
                        admin_email = settings_obj.email if settings_obj else 'help@flezpay.com'
                        send_mail(
                            subject="Paystack Bulk Transfer Exception",
                            message=f"An exception occurred during manual payroll bulk transfer.\n\nException:\n{str(e)}",
                            from_email="no-reply@flezpay.com",
                            recipient_list=[admin_email],
                            fail_silently=True,
                        )
                    except Exception:
                        pass
            
            if paystack_error:
                return Response({'status': False, 'message': paystack_error}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'status': True, 
                'message': f"Successfully processed payroll for {count} employees. Total: ₦{total_processed:,.2f}"
            })

        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)
