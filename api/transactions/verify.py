import random
from django.utils import timezone
import traceback
import requests
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from api.functions import misc, send_mail
from api.models import UserSecure, AuthenticationPin, UserDetails


class WithdrawPin(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            if not misc.enforce_permissions(request, 'manage_finances'):
                return Response({'status': False, 'message': "Access Denied: You do not have 'manage_finances' permission."}, status=status.HTTP_403_FORBIDDEN)
            user_instance = UserSecure.objects.get(user_id=user_id)

            # Check if withdrawals are disabled for acting user (e.g., staff/manager) or account owner
            actual_user_id = getattr(request, 'actual_user_id', None)
            if actual_user_id:
                actual_user = UserSecure.objects.filter(user_id=actual_user_id).first()
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

            auth_pin = "{:06d}".format(random.randint(0, 999999))

            ip_address = (
                    request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
                    or request.META.get("REMOTE_ADDR")
            )
            AuthenticationPin(user_pin=auth_pin,
                              user_phone=user_instance.user_email,
                              user_pin_type="withdrawal").save()
            location = "Unknown"
            try:
                res = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=5)
                if res.status_code == 200:
                    ip_data = res.json()
                    city = ip_data.get("city", "")
                    country = ip_data.get("country", "")
                    location = f"{city}, {country}" if city or country else "Unknown"
            except Exception as e:
                pass

            device = request.META.get("HTTP_USER_AGENT", "Unknown device")
            timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

            send_mail.mailSender(
                'trx_auth.html',
                'Withdrawal Authorization Code',
                [user_instance.user_email],
                {
                    "auth_pin": auth_pin,
                    "location": location,
                    "time": timestamp,
                    "device": device,
                }
            )
            return Response({'status': True, 'message': 'Pin sent to your number'})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            print(f"DEBUG Error in PayrollPin: {error}\n{traceback_message}")

            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


class PayrollPin(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user_instance = UserSecure.objects.get(user_id=user_id)

            # Check if withdrawals are disabled for acting user or account owner
            actual_user_id = getattr(request, 'actual_user_id', None)
            if actual_user_id:
                actual_user = UserSecure.objects.filter(user_id=actual_user_id).first()
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

            user_details = UserDetails.objects.get(user=user_instance)

            auth_pin = "{:06d}".format(random.randint(0, 999999))

            ip_address = (
                    request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
                    or request.META.get("REMOTE_ADDR")
            )
            AuthenticationPin(user_pin=auth_pin,
                              user_phone=user_instance.user_email,
                              user_pin_type="add_payroll").save()
            location = "Unknown"
            try:
                res = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=5)
                if res.status_code == 200:
                    ip_data = res.json()
                    city = ip_data.get("city", "")
                    country = ip_data.get("country", "")
                    location = f"{city}, {country}" if city or country else "Unknown"
            except Exception as e:
                pass

            device = request.META.get("HTTP_USER_AGENT", "Unknown device")
            timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

            send_mail.mailSender(
                'payroll_auth.html',
                'payroll Authorization Code',
                [user_instance.user_email],
                {
                    "auth_pin": auth_pin,
                    "location": location,
                    "time": timestamp,
                    "device": device,
                    "action_type": "Payroll details",
                    "first_name": user_details.first_name
                }
            )

            return Response({'status': True, 'message': 'Pin sent to your number'})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            print(f"DEBUG Error in PayrollPin: {error}\n{traceback_message}")

            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


class DeleteAccountPin(APIView):

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            user_instance = UserSecure.objects.get(user_id=user_id)
            user_details = UserDetails.objects.get(user=user_instance)

            auth_pin = "{:06d}".format(random.randint(0, 999999))

            ip_address = (
                    request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
                    or request.META.get("REMOTE_ADDR")
            )
            AuthenticationPin(user_pin=auth_pin,
                              user_phone=user_instance.user_email,
                              user_pin_type="delete_account").save()
            location = "Unknown"
            try:
                res = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=5)
                if res.status_code == 200:
                    ip_data = res.json()
                    city = ip_data.get("city", "")
                    country = ip_data.get("country", "")
                    location = f"{city}, {country}" if city or country else "Unknown"
            except Exception as e:
                pass

            device = request.META.get("HTTP_USER_AGENT", "Unknown device")
            timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

            send_mail.mailSender(
                'delete_account.html',
                'Account Deletion Authorization Code',
                [user_instance.user_email],
                {
                    "auth_pin": auth_pin,
                    "location": location,
                    "time": timestamp,
                    "device": device,
                }
            )
            return Response({'status': True, 'message': 'Pin sent to your email'})

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            print(f"DEBUG Error in PayrollPin: {error}\n{traceback_message}")

            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)


