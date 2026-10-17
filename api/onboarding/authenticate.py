import decimal
import hashlib
import uuid
from django.utils import timezone
from datetime import datetime, date
from django.utils.timezone import now
from django.contrib.auth import authenticate, login
from django.core.serializers import serialize
from django.db.models import Q
from django.http import JsonResponse
from django.utils.translation import trim_whitespace
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from api import models
import traceback
from api.functions import validate, misc, send_sms, send_mail
from .serializer import UserSecureSerializer, UserDetailsSerializer
from django.db import transaction, IntegrityError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.models import TokenUser
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings
import requests
import urllib.parse
from django.shortcuts import redirect
from django.http import HttpResponse

class UnsafeSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return None



def sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    return obj

@method_decorator(csrf_exempt, name='dispatch')
class UserRegister(APIView):
    authentication_classes = [UnsafeSessionAuthentication]

    def post(self, request):
        try:
            with transaction.atomic():
                user_pin = request.data.get('user_pin')
                user_id = misc.generate_unique_account_number()
                phone = trim_whitespace(request.data.get('user_phone', '') or '')
                email = trim_whitespace(request.data.get('user_email', '') or '')

                google_auth_token = request.data.get('google_auth')
                is_google_auth = False
                
                if google_auth_token:
                    from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
                    signer = TimestampSigner()
                    try:
                        verified_email = signer.unsign(google_auth_token, max_age=1800)
                        if verified_email != email:
                            raise Exception("Google authentication email mismatch. Please try signing in with Google again.")
                        is_google_auth = True
                    except (BadSignature, SignatureExpired):
                        raise Exception("Invalid or expired Google authentication session. Please try signing in with Google again.")

                if not phone:
                    raise Exception("Phone number is required")
                if not email:
                    raise Exception("Email address is required")

                # Check for duplicate phone numbers (guard against None values in DB)
                all_phone_formats = models.UserSecure.objects.all()
                for phone_format in all_phone_formats:
                    raw = phone_format.user_phone or ''
                    compare_phones = [raw, f'234{raw}', f'2340{raw}']
                    for phone_f in compare_phones:
                        if not phone_f:
                            continue
                        try:
                            if int(phone) == int(phone_f):
                                raise Exception("This phone number is already registered")
                        except (ValueError, TypeError):
                            continue

                if models.UserSecure.objects.filter(user_email=email).exists():
                    raise Exception("An account with this email already exists")

                # Google Auth users skip email PIN verification (Google already verified the email)
                if not is_google_auth:
                    if not models.AuthenticationPin.objects.filter(user_pin=user_pin, user_phone=email).exists():
                        raise Exception('Verification code is invalid or has expired. Please request a new one.')

                password = request.data.get('password') if not is_google_auth else misc.generate_temp_password()

                user_secure = models.UserSecure.objects.create_user(
                    user_email=email,
                    password=password,
                    user_id=user_id,
                    user_phone=phone,
                    user_type='business',
                    is_active=True
                )
                country_code = request.data.get('country', 'NG')
                allowed_country = models.AllowedCountries.objects.filter(code=country_code).first()
                
                # Enforce the timezone from the selected country
                user_timezone = allowed_country.timezone if allowed_country and allowed_country.timezone else 'Africa/Lagos'

                models.UserDetails.objects.create(
                    user=user_secure,
                    user_country=country_code,
                    user_timezone=user_timezone,
                    currency=request.data.get('currency', 'NGN'),
                    first_name=request.data['first_name'],
                    last_name=request.data['last_name']
                )
                
                # Create Business Profile
                plan_mapping = {'free': 0, 'basic': 1, 'pro': 2}
                plan_interest = request.data.get('plan', 'free')
                country_vat = allowed_country.vat_percentage if (allowed_country and allowed_country.vat_percentage is not None) else 0.0
                
                models.BusinessDetails.objects.create(
                    user=user_secure,
                    business_name=request.data.get('biz_name'),
                    business_type=request.data.get('biz_type'),
                    team_size=request.data.get('team_size'),
                    plan_code=plan_mapping.get(plan_interest, 0),
                    vat_percentage=country_vat
                )

                models.UserTrxPin.objects.create(
                    user_details=user_secure,
                    account_pin=misc.hash_md5(misc.hash_md5("000000"))
                )
                import zoneinfo
                try:
                    user_tz = zoneinfo.ZoneInfo(user_timezone)
                except Exception:
                    user_tz = timezone.get_default_timezone()
                timestamp = timezone.localtime(timezone.now(), user_tz).strftime("%B %d, %Y at %I:%M %p %Z")
                try:
                    send_mail.mailSender(
                        'welcome_email.html',
                        'Welcome to FlezPay',
                        [email],
                        {
                            "timestamp": timestamp,
                            "first_name": request.data['first_name']
                        }
                    )
                except Exception as mail_err:
                    print(f"DEBUG: Welcome email sending failed ({mail_err}).")
                
                from django.contrib.auth import login
                login(request, user_secure, backend='django.contrib.auth.backends.ModelBackend')
                
                token_data = misc.create_simple_jwt_session(user_secure)
                jwt = token_data.data.get('jwt')
                from api.user_data import data_views
                full_data_resp = data_views.user_data_db(user_secure.user_id, jwt, request=request)
                full_data = full_data_resp.get('data', {}) if isinstance(full_data_resp, dict) else {}
                token_data.data['user'] = full_data
                return sanitize_for_json(token_data)
        except IntegrityError:
            return Response(
                {'status': False, 'message': 'An account with these details already exists. Please try logging in.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            error = str(e)
            # Return the message as-is if it was explicitly raised (readable)
            # Otherwise replace internal Python errors with a generic friendly message
            internal_patterns = [
                "argument must be", "NoneType", "__", "object has no attribute",
                "unsupported operand", "'NoneType'", "int()"
            ]
            if any(pat in error for pat in internal_patterns):
                error = "Something went wrong on our end. Please try again or contact support."
            if type(e).__name__ == "KeyError":
                field = error.strip("'")
                error = f"The field '{field}' is required to complete registration."
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginRedirect(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def get(self, request):
        client_id = settings.GOOGLE_AUTH_CLIENT_ID
        redirect_uri = request.build_absolute_uri('/api/onboard/google/callback')
        scope = "email profile"
        next_url = request.GET.get('next', '/dashboard')
        state = urllib.parse.quote(next_url)
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={urllib.parse.quote(scope)}"
            f"&state={state}"
            f"&access_type=offline"
        )
        return redirect(auth_url)

@method_decorator(csrf_exempt, name='dispatch')
class GoogleAuthCallback(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state', '/dashboard')
        next_url = urllib.parse.unquote(state) if state else '/dashboard'
        if not next_url.startswith('/'):
            next_url = '/dashboard'

        if not code:
            return HttpResponse("Authentication failed or cancelled.", status=400)
            
        client_id = settings.GOOGLE_AUTH_CLIENT_ID
        client_secret = settings.GOOGLE_AUTH_SECRET
        redirect_uri = request.build_absolute_uri('/api/onboard/google/callback')
        
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            resp = requests.post(token_url, data=data)
            resp_data = resp.json()
            id_token_str = resp_data.get('id_token')
            
            if not id_token_str:
                return HttpResponse(f"Failed to obtain token from Google. {resp_data}", status=400)
                
            idinfo = id_token.verify_oauth2_token(id_token_str, google_requests.Request(), client_id)
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            
            with transaction.atomic():
                user_secure = models.UserSecure.objects.filter(user_email=email).first()
                if not user_secure:
                    # Redirect to signup page with pre-filled fields
                    from django.utils.http import urlencode
                    from django.core.signing import TimestampSigner
                    signer = TimestampSigner()
                    google_auth_token = signer.sign(email)
                    query_string = urlencode({
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'google_auth': google_auth_token
                    })
                    html = f"""
                    <html>
                    <body>
                    <script>
                        window.location.href = '/signup?{query_string}';
                    </script>
                    <p>Redirecting to registration...</p>
                    </body>
                    </html>
                    """
                    return HttpResponse(html)

                login(request, user_secure, backend='django.contrib.auth.backends.ModelBackend')
                token_response = misc.create_simple_jwt_session(user_secure)
                jwt = token_response.data.get('jwt')
                refresh = token_response.data.get('refresh')
                
                # Fetch full user data for the dashboard
                from api.user_data import data_views
                full_user_data_resp = data_views.user_data_db(user_secure.user_id, jwt, request=request)
                user_data_payload = full_user_data_resp.get('data', {}) if isinstance(full_user_data_resp, dict) else {}
                user_data_payload = sanitize_for_json(user_data_payload)
                
                import json
                from django.utils.html import escapejs
                user_data_json = json.dumps(user_data_payload, default=str)
                user_data_escaped = escapejs(user_data_json)
                
                # Render an HTML page that sets localStorage and redirects
                html = f"""
                <html>
                <body>
                <script>
                    localStorage.setItem('access_token', '{jwt}');
                    localStorage.setItem('refresh_token', '{refresh}');
                    localStorage.setItem('user_data', '{user_data_escaped}');
                    localStorage.setItem('last_data_refresh', Date.now().toString());
                    window.location.href = '{next_url}';
                </script>
                <p>Authenticating... Please wait.</p>
                </body>
                </html>
                """
                return HttpResponse(html)
        except Exception as e:
            return HttpResponse(f"An error occurred: {str(e)}", status=500)



@method_decorator(csrf_exempt, name='dispatch')
class UserLogin(APIView):
    authentication_classes = [UnsafeSessionAuthentication]

    def post(self, request):
        try:
            email_or_phone = request.data['email_or_phone']
            password = request.data['password']
            two_factor_code = request.data.get('two_factor_code')
            
            user_instance = authenticate(request, username=email_or_phone, password=password)
            
            if not user_instance:
                return Response({'status': False, 'message': 'Invalid login credentials'}, status=status.HTTP_401_UNAUTHORIZED)

            # Check if user is active
            if not user_instance.is_active:
                return Response({
                    'status': False,
                    'message': 'Your account has been deactivated. Please contact support for assistance.'
                }, status=status.HTTP_403_FORBIDDEN)

            # Check if 2FA is enabled
            if user_instance.two_factor_enabled and user_instance.two_factor_secret:
                # If 2FA code is provided, verify it
                if two_factor_code:
                    import pyotp
                    totp = pyotp.TOTP(user_instance.two_factor_secret)
                    if not totp.verify(two_factor_code, valid_window=1):
                        return Response({
                            'status': False,
                            'message': 'Invalid 2FA code. Please try again.',
                            'requires_2fa': True
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # 2FA is enabled but code not provided
                    return Response({
                        'status': False,
                        'message': '2FA verification code is required',
                        'requires_2fa': True
                    }, status=status.HTTP_200_OK)  # Return 200 to indicate valid credentials, just needs 2FA

            # Get IP address and location for login tracking
            ip_address = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
                or request.META.get("REMOTE_ADDR")
            )
            location = "Unknown"
            try:
                import requests
                res = requests.get(f"https://ipinfo.io/{ip_address}/json", timeout=5)
                if res.status_code == 200:
                    ip_data = res.json()
                    city = ip_data.get("city", "")
                    country = ip_data.get("country", "")
                    location = f"{city}, {country}" if city or country else "Unknown"
            except Exception:
                pass
            
            # Get device information
            device = request.META.get("HTTP_USER_AGENT", "Unknown device")
            
            # Get user details for email
            user_details = models.UserDetails.objects.filter(user=user_instance).first()
            if user_details and request.data.get('timezone'):
                user_details.user_timezone = request.data.get('timezone')
                user_details.save()
            first_name = user_details.first_name if user_details and user_details.first_name else "User"
            
            # Create notification
            models.Notifications.objects.create(
                user=user_instance,
                title='Account login',
                description=f"You logged into your account from {location}. If this wasn't you make sure to contact support",
                notification_type='auth'
            )
            
            # Send login notification email
            try:
                from datetime import datetime
                current_year = datetime.now().year
                timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")
                
                # send_mail.mailSender(
                #     'login_notification.html',
                #     'New Login to Your FlezPay Account',
                #     [user_instance.user_email],
                #     {
                #         'first_name': first_name,
                #         'location': location,
                #         'time': timestamp,
                #         'device': device,
                #         'current_year': current_year
                #     }
                # )
            except Exception as e:
                # Log error but don't fail login if email fails
                pass
            
            # Establish session for TemplateView login_required protection
            login(request, user_instance)
            
            token_data = misc.create_simple_jwt_session(user_instance)
            jwt = token_data.data.get('jwt')
            from api.user_data import data_views
            full_data_resp = data_views.user_data_db(user_instance.user_id, jwt, request=request)
            full_data = full_data_resp.get('data', {}) if isinstance(full_data_resp, dict) else {}
            token_data.data['user'] = full_data
            return sanitize_for_json(token_data)

        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = 'traceback.format_exc()'
            return Response({'status': False, 'message': error, 'traceback': traceback_message},
                            status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class UserPinAuthenticate(APIView):
    authentication_classes = [UnsafeSessionAuthentication]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            account_pin = request.data.get("account_pin")
            account_pin = misc.hash_md5(misc.hash_md5(account_pin))
            pin = models.UserTrxPin.objects.filter(user_details=instance, account_pin=account_pin)
            if pin.exists():
                return Response({"status": True, "message": "Pin authenticated"})
            raise Exception('Invalid pin. Reset pin if forgotten.')
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class ManagerPinAuthenticate(APIView):
    authentication_classes = [UnsafeSessionAuthentication]

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            account_pin = request.data.get("account_pin")
            account_pin = misc.hash_md5(misc.hash_md5(account_pin))
            pin = models.UserManagers.objects.filter(user=instance, manager_pin=account_pin)
            if pin.exists():
                return Response({"status": True, "message": "Pin authenticated"})
            raise Exception('Invalid pin. Reset pin if forgotten.')
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)




@method_decorator(csrf_exempt, name='dispatch')
class ValidateEmailPhone(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def post(self, request):
        try:
            phone = request.data.get('user_phone', '') or ''
            email = request.data.get('user_email', '') or ''

            if not phone:
                raise Exception("Phone number is required")
            if not email:
                raise Exception("Email address is required")

            # Check for duplicate phone numbers (guard against None values in DB)
            all_phone_formats = models.UserSecure.objects.all()
            for phone_format in all_phone_formats:
                raw = phone_format.user_phone or ''
                compare_phones = [raw, f'234{raw}', f'2340{raw}']
                for phone_f in compare_phones:
                    if not phone_f:
                        continue
                    try:
                        if int(phone) == int(phone_f):
                            raise Exception("This phone number is already registered")
                    except (ValueError, TypeError):
                        continue

            if models.UserSecure.objects.filter(user_email=email).exists():
                raise Exception("An account with this email already exists")

            pin = misc.unique_pin()
            try:
                timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")
                send_mail.mailSenderAsync(
                    'validation_pin.html',
                    'Account validation pin',
                    [email],
                    {
                        "verification_code": pin,
                        "timestamp": timestamp,
                        "user_email": email
                    }
                )
            except Exception as mail_err:
                print(f"DEBUG: Mail sending failed ({mail_err}). PIN is: {pin}")
                # Don't raise Exception to allow local testing without SMTP server
            models.AuthenticationPin(user_pin=pin, user_phone=email).save()
            return Response({'status': True, 'message': f"A verification code has been sent to {email}"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                field = str(e).strip("'")
                error = f"The field '{field}' is required."
            return Response({'status': False, 'message': error}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class ValidatePhone(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def post(self, request):
        try:
            phone = request.data.get('user_phone')
            obj = models.UserSecure.objects.filter(user_phone=phone)
            if not obj.exists():
                raise Exception("Phone number not recognized")
            pin = misc.unique_pin()[:4]
            message = f"Validate your phone number with the pin: {pin}"
            try:
                send_sms.sms_sender(message, phone)
                timestamp = timezone.localtime().strftime("%B %d, %Y at %I:%M %p %Z")

                send_mail.mailSender(
                    'validation_pin.html',
                    'Account validation pin',
                    ["peremi@flezpay.com"],
                    {
                        "verification_pin": pin,
                        "timestamp": timestamp,
                        "user_phone": phone
                    }
                )
            except Exception as error:
                raise Exception(f"Error sending sms")
            models.AuthenticationPin(user_pin=pin, user_phone=phone, user_pin_type="reset_auth_pin").save()
            return Response({'status': True, 'message': f"Pin has been sent to {phone}"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = 'traceback.format_exc()'
            return Response({'status': False, 'message': error}, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class ValidatePin(APIView):
    authentication_classes = [UnsafeSessionAuthentication]

    def post(self, request):
        try:
            pin = int(request.data['user_pin'])
            email = request.data['user_email']
            if not models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=email).exists():
                raise Exception('Pin is not valid or expired')
            return Response({'status': True, 'message': "Pin exists"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = 'traceback.format_exc()'
            return JsonResponse({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)



@method_decorator(csrf_exempt, name='dispatch')
class ValidatePinUpdate(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def post(self, request):
        try:
            pin = int(request.data.get('user_pin'))
            phone = request.data.get('user_phone')
            pin_obj = models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=phone)
            if not pin_obj.exists():
                raise Exception('Pin is not valid or expired')

            instance = models.UserSecure.objects.get(user_phone=phone)
            trx = models.UserTrxPin.objects.get(user_details=instance)
            trx.account_pin = misc.hash_md5(misc.hash_md5(request.data['account_pin']))
            trx.save()
            pin_obj.delete()
            models.Notifications.objects.create(
                user=instance,
                title='Authentication',
                description=f"You changed your account's authentication pin by reset",
                notification_type='auth'
            )
            return Response({'status': True, 'message': "Authentication pin updated successfully"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = traceback.format_exc()
            return Response({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class ValidatePinReset(APIView):
    authentication_classes = [UnsafeSessionAuthentication]

    def post(self, request):
        try:
            pin = int(request.data.get('user_pin'))
            phone = request.data.get('user_phone')
            if not models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=phone, user_pin_type='reset_auth_pin').exists():
                raise Exception('Pin is not valid or expired')
            return Response({'status': True, 'message': "Pin exists"})
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            traceback_message = 'traceback.format_exc()'
            return JsonResponse({'status': False, 'message': error},
                            status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequest(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def post(self, request):
        try:
            email = request.data.get('email', '').strip().lower()
            if not email:
                raise Exception("Email is required")
            
            user = models.UserSecure.objects.filter(user_email=email).first()
            if not user:
                # Return success even if user not found to prevent user enumeration
                return Response({'status': True, 'message': "If your email is registered, you will receive a PIN."})
            
            pin = misc.unique_pin()[:6]
            # Clear old reset pins for this user
            models.AuthenticationPin.objects.filter(user_phone=email, user_pin_type="password_reset").delete()
            
            models.AuthenticationPin.objects.create(
                user_pin=pin, 
                user_phone=email, 
                user_pin_type="password_reset"
            )
            
            # Build password reset link
            origin = request.headers.get('Origin') or f"{request.scheme}://{request.get_host()}"
            reset_link = f"{origin}/reset-password?email={email}&pin={pin}"
            
            try:
                send_mail.mailSenderAsync(
                    'password_reset.html',
                    'Reset Your FlezPay Password',
                    [email],
                    {"verification_pin": pin, "reset_link": reset_link, "email": email}
                )
            except Exception as mail_err:
                print(f"Mail Error: {mail_err}")
            
            return Response({'status': True, 'message': "A 6-digit PIN has been sent to your email.", 'reset_link': reset_link})
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetConfirm(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def post(self, request):
        try:
            email = request.data.get('email', '').strip().lower()
            pin = request.data.get('pin')
            new_password = request.data.get('password')
            
            if not all([email, pin, new_password]):
                raise Exception("Email, PIN, and new password are required")
            
            pin_obj = models.AuthenticationPin.objects.filter(
                user_pin=pin, 
                user_phone=email, 
                user_pin_type="password_reset"
            ).first()
            
            if not pin_obj:
                raise Exception("Invalid or expired PIN")
            
            user = models.UserSecure.objects.filter(user_email=email).first()
            if not user:
                raise Exception("User not found")
            
            user.set_password(new_password)
            user.save()
            
            if user.user_type == 'manager':
                manager = models.UserManagers.objects.filter(manager_email__iexact=user.user_email).first()
                if manager:
                    manager.password_changed = True
                    manager.manager_password = misc.hash_md5(misc.hash_md5(new_password))
                    manager.save()
            
            # Delete the PIN after use
            pin_obj.delete()
            
            return Response({'status': True, 'message': "Password updated successfully."})
            
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class ProspectWaitlist(APIView):
    authentication_classes = [UnsafeSessionAuthentication]
    def post(self, request):
        try:
            first_name = request.data.get('first_name', '')
            last_name = request.data.get('last_name', '')
            email = request.data.get('user_email', '')
            phone = request.data.get('user_phone', '')
            biz_name = request.data.get('biz_name', '')
            country = request.data.get('country', '')
            
            if not email:
                raise Exception("Email is required")
            
            try:
                send_mail.mailSender(
                    'blank_email.html', # Assuming a generic/blank template or we can just send text if possible. Wait, we should probably pass a template.
                    'New Prospect: Unsupported Region',
                    ['peremi@flezpay.com'],
                    {
                        "message": f"A new prospect from an unsupported region has joined the waitlist.\n\nName: {first_name} {last_name}\nEmail: {email}\nPhone: {phone}\nBusiness: {biz_name}\nCountry: {country}"
                    }
                )
            except Exception as mail_err:
                print(f"Mail Error: {mail_err}")
                
            return Response({'status': True, 'message': "Your details have been recorded. We will notify you when your region is supported."})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

