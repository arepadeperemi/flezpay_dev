from rest_framework.views import APIView
import traceback
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from api.functions import misc
from api import models
from api.user_data.data_views import calculate_total_balance


class Transfer(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_finances'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_finances' permission."}, status=status.HTTP_403_FORBIDDEN)
            with transaction.atomic():
                try:
                    instance = models.UserSecure.objects.get(user_id=user_id)
                    details = models.UserDetails.objects.get(user=instance)
                    balance = calculate_total_balance(instance)
                    data = request.data.copy()

                    collection_id = data.get('collection_id')
                    recipient_id = data.get('recipient_id')
                    deposit_instance = models.UserSecure.objects.get(user_id=recipient_id)
                    amount = data.get('amount')
                    currency = details.user_country
                    source = data.get('trx_source', '')
                except Exception:
                    raise Exception("Invalid operation")


                # Check if transfers are disabled for acting user (e.g., staff/manager) or account owner
                actual_user_id = getattr(request, 'actual_user_id', None)
                if actual_user_id:
                    actual_user = models.UserSecure.objects.filter(user_id=actual_user_id).first()
                    if actual_user and actual_user.transfers_disabled:
                        raise Exception('Transfers have been temporarily disabled for your account. Please contact support for assistance.')

                if instance.transfers_disabled:
                    raise Exception('Transfers have been temporarily disabled for your account. Please contact support for assistance.')

                if recipient_id == instance.user_id:
                    raise Exception('Impossible operation')
                
                if not isinstance(amount, (int, float)) or (isinstance(amount, str) and amount.replace('.', '', 1).isdigit()):
                    raise Exception('amount must be a valid number')
                
                if amount > balance:
                    raise Exception('Insufficient balance')

                if amount <= 0:
                    raise Exception('Invalid amount')
                
                # Transfer from
                transfer = models.UserTransactions.objects.create(
                    user=instance,
                    trx_status='completed',
                    trx_amount=amount,
                    trx_type='transfer',
                    trx_source=source,
                    trx_currency=currency,
                    description=f'Transfer',
                    user_collection_id=recipient_id,
                    destination_id = deposit_instance.uniq_id
                )

                # Backup transaction
                models.TransactionBackup.objects.create(
                    trx_uniq=transfer,
                    trx_amount=amount,
                    trx_id=transfer.trx_id,
                    sender=instance.user_id,
                    recipient=recipient_id,
                    trx_currency=currency
                )
                models.Notifications.objects.create(
                    user=instance,
                    title='Transfer',
                    description= f'You made a transfer of {currency}{amount} to {details.first_name} {details.last_name}',
                    notification_type='tranc_success'
                )

                # Deposit to
                models.UserTransactions.objects.create(
                    user=deposit_instance,
                    trx_status='completed',
                    trx_amount=amount,
                    trx_type='credit',
                    trx_currency=currency,
                    description=f'Credit transaction from {details.first_name} {details.last_name}',
                    trx_source = instance.uniq_id,
                    user_collection_id=collection_id,
                    destination_id=instance.uniq_id
                )
                models.Notifications.objects.create(
                    user=deposit_instance,
                    title='Credit',
                    description= f'You recieved a transfer of {currency}{amount} from {details.first_name} {details.last_name}',
                    notification_type='tranc_success'
                )
                
                return Response({'status': True, 'message': 'Transaction successful'})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)
        

def deposit():
    pass