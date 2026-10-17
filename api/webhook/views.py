import os.path
import hmac, hashlib, os, json, traceback
from pathlib import Path
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from api import models
from api.external.psb_api import PSB
from api.models import BankDepositDetails
from datetime import datetime
from paystackease import PayStackWebhook, PayStackSignatureVerifyError
from dotenv import load_dotenv
import logging
import requests

load_dotenv()
logger = logging.getLogger(__name__)


def forward_webhook_to_logistics(raw_body, signature, event_type):
    """
    Forward Paystack webhook to logistics backend for developer order processing.
    Only forwards relevant events: charge.success, charge.failed, transfer.success, transfer.failed, transfer.reversed
    """
    # Events to forward to logistics backend
    forwardable_events = [
        'charge.success',
        'charge.failed',
        'transfer.success',
        'transfer.failed',
        'transfer.reversed'
    ]
    
    if event_type not in forwardable_events:
        logger.info(f"Skipping webhook forward for event type: {event_type}")
        return
    
    # Get logistics backend webhook URL from environment
    logistics_webhook_url = os.getenv('LOGISTICS_WEBHOOK_URL')
    
    if not logistics_webhook_url:
        logger.warning("LOGISTICS_WEBHOOK_URL not set in environment. Skipping webhook forward.")
        return
    
    try:
        # Forward the webhook with original signature and body
        headers = {
            'Content-Type': 'application/json',
            'X-Paystack-Signature': signature,  # Preserve original signature
            'X-Forwarded-From': 'flezpay-backend',  # Identify the forwarder
        }
        
        response = requests.post(
            logistics_webhook_url,
            data=raw_body,  # Send raw body to preserve signature verification
            headers=headers,
            timeout=10  # 10 second timeout
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully forwarded {event_type} webhook to logistics backend")
        else:
            logger.warning(
                f"Logistics backend returned {response.status_code} for {event_type}: {response.text}"
            )
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout forwarding {event_type} webhook to logistics backend")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding {event_type} webhook to logistics backend: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error forwarding {event_type} webhook: {e}")


class PSB_WEBHOOK(APIView):

    def post(self, request):
        data = request.data.copy()
        try:
            try:
                # Get account number
                query = BankDepositDetails.objects.get(account_reference=data['transaction']['reference'])
                account_number = query.account_number
            except BankDepositDetails.DoesNotExist:
                return Response({'code': '99', 'message': 'Invalid reference'}, status=status.HTTP_400_BAD_REQUEST)

            # Call Celery task to handle the webhook response and confirmation asynchronously
            from api.tasks import process_psb_webhook_task
            process_psb_webhook_task.delay(data, account_number)

            return Response({'code': '00', 'message': 'success'})

        except Exception as e:
            return Response({'code': 'S1', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class Paystack_WEBHOOK(APIView):
    def post(self, request):
        raw_body = request.body
        signature = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
        # data = request.data.copy()

        try:
            secret = os.getenv("PAYSTACK_PRIVATE_KEY")
            if not secret:
                return Response(
                    {"status": False, "message": "PAYSTACK_PRIVATE_KEY not set"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Validate payload
            try:
                event = PayStackWebhook.get_event_data(secret, raw_body, signature)
            except (ValueError, PayStackSignatureVerifyError) as error:
                return Response(
                    {"status": False, "message": str(error)},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            data = request.data.copy()
            charge_data = data.get("data", {})
            
            # Forward webhook to logistics backend (async, non-blocking)
            # This happens after signature verification but before local processing
            try:
                from api.tasks import forward_webhook_to_logistics_task
                # Pass decoded body to Celery task
                forward_webhook_to_logistics_task.delay(raw_body.decode('utf-8'), signature, event.type)
            except Exception as forward_error:
                logger.error(f"Webhook task dispatch failed: {forward_error}")

            # Handle charge success
            if event.type == "charge.success":
                try:
                    amount = int(charge_data.get("amount", 0)) / 100
                    account_number = charge_data.get("metadata", {}).get("receiver_account_number")
                    bank_name = charge_data.get("metadata", {}).get("receiver_bank")
                    sender_name = charge_data.get("authorization", {}).get("sender_name")
                    sender_bank = charge_data.get("authorization", {}).get("sender_bank")
                    reference = charge_data.get("reference")
                    currency = charge_data.get("currency")
                    
                    # Handle online store checkout webhook
                    if reference and str(reference).startswith("INV-"):
                        invoice = models.UserInvoices.objects.filter(invoice_id=reference).first()
                        if invoice:
                            if invoice.invoice_status != 'completed':
                                invoice.invoice_status = 'completed'
                                invoice.delivery_status = 'processing'
                                invoice.save(update_fields=['invoice_status', 'delivery_status'])
                                
                                # Deduct stock on payment confirmation for all invoice types
                                from api.user_data.inventory_helpers import deduct_invoice_stock
                                deduct_invoice_stock(invoice)
                                
                                amount_to_credit = amount
                                if invoice.delivery_type == 'system':
                                    delivery_item = invoice.invoice_items.filter(item_id='DELIVERY_001').first()
                                    delivery_fee = float(delivery_item.item_amount) if delivery_item else 0.0
                                    amount_to_credit = max(0.0, amount - delivery_fee)
                                    
                                    has_physical_items = False
                                    for inv_item in invoice.invoice_items.exclude(item_id__in=['TAX_001', 'DELIVERY_001']):
                                        b_item = models.UserItems.objects.filter(item_id=inv_item.item_id).first()
                                        if b_item and not b_item.is_digital:
                                            has_physical_items = True
                                            break
                                    if has_physical_items:
                                        from api.functions.logistics import process_store_waybill
                                        process_store_waybill(invoice)
                                
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
                                    description=f"Order #{invoice.invoice_id} has been paid ({currency}{amount:,.2f}). Please fulfil it.",
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
                                    {"invoice": invoice, "invoice_items": invoice_items, "amount": amount, "currency": currency}
                                )
                                
                                # Send receipt & digital product attachments to customer
                                from api.user_data.data_update import send_customer_order_receipt_async
                                send_customer_order_receipt_async(invoice.invoice_id)
                            return Response({"status": True, "message": "success"})
                        else:
                            return Response({"status": False, "message": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

                    deposit_account = models.BankDepositDetails.objects.get(
                        account_number=account_number
                    )
                    user = deposit_account.user
                    instance = models.UserSecure.objects.get(user_id=user)
                    details = models.UserDetails.objects.get(user=instance)
                    collection_id = deposit_account.collection_id or account_number

                    # Prevent duplicate transactions
                    if models.UserTransactions.objects.filter(
                        description=reference
                    ).exists():
                        return Response(
                            {"status": False, "message": "Duplicate transaction"},
                            status=status.HTTP_207_MULTI_STATUS,
                        )
                except Exception as e:
                    logger.exception(str(e))
                    return Response(
                        {"status": False, "message": "Unknown deposit account"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

                # Create transaction
                try:
                    transfer = models.UserTransactions.objects.create(
                        user=instance,
                        trx_status="completed",
                        trx_amount=amount,
                        trx_type="credit",
                        trx_source=sender_name or sender_bank,
                        trx_currency=currency,
                        description=reference,
                        user_collection_id=collection_id,
                        destination_id=instance.uniq_id,
                    )

                    # Backup transaction
                    models.TransactionBackup.objects.create(
                        trx_uniq=transfer,
                        trx_amount=amount,
                        trx_id=transfer.trx_id,
                        sender=instance.user_id,
                        recipient=instance.user_id,
                        trx_currency=currency,
                    )
                except Exception as error:
                    logger.exception(str(error))
                    return Response(
                        {"status": False, "message": str(error)},
                        status=status.HTTP_204_NO_CONTENT,
                    )

            # ------------------ WITHDRAWALS AND PAYOUTS ------------------
            elif event.type == "transfer.success":
                reference = charge_data.get("reference")
                try:
                    transaction = models.UserTransactions.objects.get(
                        description=reference,
                        trx_type__in=["withdrawal", "payment"]
                    )
                    transaction.trx_status = "completed"
                    transaction.save(update_fields=["trx_status"])
                except models.UserTransactions.DoesNotExist:
                    logger.warning(f"Transfer transaction not found for reference {reference}")
                    return Response(
                        {"status": False, "message": "Transfer transaction not found for reference"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

            elif event.type == "transfer.failed":
                reference = data.get("reference", "") or charge_data.get("reference", "")
                try:
                    trx = models.UserTransactions.objects.get(description__icontains=reference)
                    trx.trx_status = "failed"
                    trx.save(update_fields=["trx_status"])
                    
                    trx_label = "Payroll Disbursement" if trx.trx_type == "payment" else "Withdrawal"

                    models.Notifications.objects.create(
                        user=trx.user,
                        title=f"{trx_label} Failed",
                        description=f"Your {trx_label.lower()} of {trx.trx_currency}{trx.trx_amount:.2f} failed",
                        notification_type="tranc_failed",
                    )
                except models.UserTransactions.DoesNotExist:
                    logger.warning(f"No local transaction found for failed transfer {reference}")
                    return Response(
                        {"status": False, "message": f"No local transaction found for failed transfer {reference}"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

            elif event.type == "transfer.reversed":
                reference = data.get("reference", "") or charge_data.get("reference", "")
                try:
                    trx = models.UserTransactions.objects.get(description__icontains=reference)
                    trx.trx_status = "failed"
                    trx.save(update_fields=["trx_status"])
                    
                    trx_label = "Payroll Disbursement" if trx.trx_type == "payment" else "Withdrawal"

                    models.Notifications.objects.create(
                        user=trx.user,
                        title=f"{trx_label} Reversed",
                        description=f"Your {trx_label.lower()} of {trx.trx_currency}{trx.trx_amount:.2f} was reversed",
                        notification_type="tranc_info",
                    )
                except models.UserTransactions.DoesNotExist:
                    logger.warning(f"No local transaction found for reversed transfer {reference}")
                    return Response(
                        {"status": False, "message": f"No local transaction found for reversed transfer {reference}"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )

            return Response({"status": True, "message": "success"})

        except Exception as e:
            logger.exception(str(e))
            return Response(
                {"status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )