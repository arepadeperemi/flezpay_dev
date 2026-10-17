import traceback

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api import models
from api.user_data.serializer import UserItemsSerializer, UserSecureSerializer, UserDetailSerializer


class ScanPrice(APIView):

    def post(self, request):
        try:
            item_id = request.data['id']
            queryset = models.UserItems.objects.filter(item_id=item_id)
            if not queryset.exists():
                raise Exception('Product is not listed with us')
            serializer = UserItemsSerializer(queryset.first())
            data = serializer.data
            return Response({'status': True, 'data': data})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


class ScanPayment(APIView):

    def post(self, request):
        try:
            user_id = request.data['id']
            obj = models.UserSecure.objects.filter(user_id=user_id)
            if not obj.exists():
                raise Exception("Not a valid FlezPay ID")
            else:
                queryset = models.UserDetails.objects.get(user_id=obj.first().uniq_id)
                serializer = UserDetailSerializer(queryset)
                data = serializer.data
                return Response({'status': True, 'data': data})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)
        
