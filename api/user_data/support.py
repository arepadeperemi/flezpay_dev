import traceback
from rest_framework import status
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api import models
from api.functions import misc
from api.models import UserItems, UserVerificationDetails
from api.user_data.serializer import (
    FaqSerializer, SupportSerializer
)


class AddFaq(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            data = request.data
            serializer = FaqSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Faq added successfully"})
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
        

class AddSupport(APIView):
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            data = request.data
            support_obj, created = models.UserSupport.objects.update_or_create(
                uniq_id=1, defaults=data
            )
            action = "added" if created else "updated"
            return Response({'status': True, 'message': f"Support {action} successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)