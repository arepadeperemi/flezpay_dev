import traceback
import base64
import qrcode
from io import BytesIO
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from api import models
from api.functions import misc
import pyotp


class TwoFactorAuthSetup(APIView):
    """Generate 2FA secret and QR code for setup"""

    def get(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            user_details = models.UserDetails.objects.filter(user=instance).first()
            
            # Generate a new secret if user doesn't have one or wants to reset
            if not instance.two_factor_secret:
                secret = pyotp.random_base32()
                instance.two_factor_secret = secret
                instance.save(update_fields=['two_factor_secret'])
            else:
                secret = instance.two_factor_secret
            
            # Get user email for the QR code label
            user_email = instance.user_email or f"user_{user_id}"
            user_name = user_details.first_name if user_details else "User"
            
            # Create TOTP object
            totp = pyotp.TOTP(secret)
            
            # Generate provisioning URI for QR code
            provisioning_uri = totp.provisioning_uri(
                name=user_email,
                issuer_name="FlezPay"
            )
            
            # Generate QR code image
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer)
            buffer.seek(0)
            
            # Convert to base64 for frontend
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return Response({
                'status': True,
                'secret': secret,
                'qr_code': f'data:image/png;base64,{img_base64}',
                'manual_entry_key': secret,  # For manual entry
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorAuthVerify(APIView):
    """Verify 2FA code during setup and enable 2FA"""

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            code = request.data.get('code')
            
            if not code:
                return Response({
                    'status': False,
                    'message': 'Verification code is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not instance.two_factor_secret:
                return Response({
                    'status': False,
                    'message': '2FA secret not found. Please generate a new one.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify the code
            totp = pyotp.TOTP(instance.two_factor_secret)
            is_valid = totp.verify(code, valid_window=1)  # Allow 1 time step window
            
            if is_valid:
                # Enable 2FA
                instance.two_factor_enabled = True
                instance.save(update_fields=['two_factor_enabled'])
                
                # Update privacy settings as well
                if not instance.privacy_settings:
                    instance.privacy_settings = {}
                instance.privacy_settings['two_factor_enabled'] = True
                instance.save(update_fields=['privacy_settings'])
                
                return Response({
                    'status': True,
                    'message': '2FA has been enabled successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': False,
                    'message': 'Invalid verification code. Please try again.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorAuthDisable(APIView):
    """Disable 2FA for user"""

    def post(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            # Verify with code before disabling
            code = request.data.get('code')
            if code and instance.two_factor_secret:
                totp = pyotp.TOTP(instance.two_factor_secret)
                if not totp.verify(code, valid_window=1):
                    return Response({
                        'status': False,
                        'message': 'Invalid verification code. Cannot disable 2FA.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Disable 2FA
            instance.two_factor_enabled = False
            instance.two_factor_secret = None  # Clear the secret
            instance.save(update_fields=['two_factor_enabled', 'two_factor_secret'])
            
            # Update privacy settings
            if not instance.privacy_settings:
                instance.privacy_settings = {}
            instance.privacy_settings['two_factor_enabled'] = False
            instance.save(update_fields=['privacy_settings'])
            
            return Response({
                'status': True,
                'message': '2FA has been disabled successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorAuthStatus(APIView):
    """Get 2FA status for user"""

    def get(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            return Response({
                'status': True,
                'two_factor_enabled': instance.two_factor_enabled or False,
                'has_secret': bool(instance.two_factor_secret)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorAuthVerifyLogin(APIView):
    """Verify 2FA code during login"""

    def post(self, request):
        try:
            email_or_phone = request.data.get('email_or_phone')
            code = request.data.get('code')
            
            if not code:
                return Response({
                    'status': False,
                    'message': 'Verification code is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Find user by email or phone
            try:
                user_secure = models.UserSecure.objects.filter(user_phone=email_or_phone).first()
                if not user_secure:
                    user_secure = models.UserSecure.objects.filter(user_email=email_or_phone).first()
            except:
                user_secure = None
            
            if not user_secure:
                return Response({
                    'status': False,
                    'message': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            if not user_secure.two_factor_enabled or not user_secure.two_factor_secret:
                return Response({
                    'status': False,
                    'message': '2FA is not enabled for this account'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify the code
            totp = pyotp.TOTP(user_secure.two_factor_secret)
            is_valid = totp.verify(code, valid_window=1)
            
            if is_valid:
                # Create session and return tokens
                from api.user_data.data_views import sanitize_for_json
                return sanitize_for_json(misc.create_simple_jwt_session(user_secure))
            else:
                return Response({
                    'status': False,
                    'message': 'Invalid verification code. Please try again.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)

