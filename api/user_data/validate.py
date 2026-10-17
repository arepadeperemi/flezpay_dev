import traceback
from rest_framework import status
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api import models
from api.functions import misc, send_mail
from api.user_data.serializer import UserSecureSerializer


class ValidateEmail(APIView):
    
    def post(self, request):
        try:
            email = request.data['user_email']
            pin = misc.unique_pin()[:4]
            user_id = misc.get_id(request)
            secure_instance = models.UserSecure.objects.get(user_id=user_id)
            serializer = UserSecureSerializer(secure_instance, data=request.data, partial=True)
            if serializer.is_valid():
                models.AuthenticationPin(user_pin=pin, user_phone=email).save()
                send_mail.mailSender( 'email_otp.html', "Email verification",[email], {"pin": pin})
                return Response({'status': True, 'message': "Validation pin sent to your email address"})
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


class ValidateEmailPin(APIView):

    def patch(self, request):
        try:
            pin = int(request.data['user_pin'])
            email = request.data['user_email']
            user_id = misc.get_id(request)
            secure_instance = models.UserSecure.objects.get(user_id=user_id)
            serializer = UserSecureSerializer(secure_instance, data=request.data, partial=True)
            if not models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=email).exists():
                raise Exception('Pin is not valid or expired')
            if serializer.is_valid():
                serializer.save()
                return Response({'status': True, 'message': "Email validated successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = 'traceback.format_exc()'
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)