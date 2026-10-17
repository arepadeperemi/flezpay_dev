from datetime import datetime

from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from api import models
from api.functions import misc, send_mail
from api.user_data.serializer import DemoRequestsSerializer


class GenerateReportView(APIView):

    def post(self, request):
        try:
            user_id = misc.get_simple_jwt_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            try:
                from api.functions.subscription_validation import SubscriptionManager, SubscriptionLimitError
                SubscriptionManager(instance).require_business_reporting()
            except SubscriptionLimitError as e:
                return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
                
            start_date  = request.data.get("start")
            end_date = request.data.get("end")
            # trx_queryset = models.UserTransactions.objects.filter(user=instance, timestamp__gte=start_date, timestamp__lt=end_date).order_by('-id')
            # serializer = UserTransactionsSerializer(trx_queryset, many=True)
            data = {}
            return Response({'status': True, 'message': "If there is an email associated with this account, report will be sent", "data": data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)



class DemoRequestView(APIView):

    def post(self, request):
        try:
            data = request.data.copy()
            name = data.get('full_name', None)
            email = data.get('email', None)
            phone = data.get('phone', None)
            state_city = data.get('state_city', None)
            demo_type = data.get('demo_type', None)
            current_year = datetime.now().year

            # queryset = models.DemoRequests()
            serializer = DemoRequestsSerializer(data=data)

            if name is None or email is None or phone is None or state_city is None or demo_type is None:
                raise Exception('All fields are required')

            if serializer.is_valid():
                serializer.save()

            # Internal mail
            send_mail.mailSender(
                'demo_request_external.html',
                'Demo request completed',
                [email],
                {'name': name,
                 'current_year': current_year}
            )

            # Customer mail
            send_mail.mailSender(
                'demo_request_internal.html',
                'Demo request',
                ['info@flezpay.com'],
                {"email": email, 'name': name, 'phone': phone, 'demo_type': demo_type,
                 'state_city': state_city, 'current_year': current_year}
            )

            return Response({'status': True, 'message': "If there is an email associated with this account, report will be sent", "data": data})
        except Exception as e:
            return Response({'status': False, 'message': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)