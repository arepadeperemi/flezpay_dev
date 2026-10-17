from rest_framework.views import APIView
import traceback
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from api.functions import misc
from api import models
from api.user_data.data_views import calculate_total_balance
from api.user_data.serializer import UserTransactionsSerializer


class TransactionDetails(APIView):

    def post(self, request):
        try:
            # user_id = misc.get_id(request)
            # instance = models.UserSecure.objects.get(user_id=user_id)
            trx_id = request.data['trx_id']
            trx = models.UserTransactions.objects.filter(trx_id=trx_id)
            if not trx.exists():
                raise Exception('Invalid transaction ID')
            
            data = UserTransactionsSerializer(trx.first()).data
            return Response({'status': True, 'message': 'Transaction details', 'data': data})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)
        
