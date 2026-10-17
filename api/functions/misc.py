import hashlib
import random
from rest_framework.authtoken.models import Token
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from api import models
from rest_framework_simplejwt.tokens import RefreshToken, Token, AccessToken
from django.contrib.auth import get_user
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
import secrets
import string


def generate_temp_password(length: int = 10) -> str:
    """
    Generate a secure temporary password.
    Default length is 12 characters.
    """
    if length < 8:
        raise ValueError("Password length should be at least 8 characters.")

    # Define character pools
    alphabet = string.ascii_letters + string.digits + string.punctuation

    # Use secrets.choice for cryptographically secure randomness
    password = ''.join(secrets.choice(alphabet) for _ in range(length))

    return password


def generate_unique_pin(existing_pins):
    while True:
        # Generate a random six-digit PIN
        pin = str(random.randint(100000, 999999))
        # Check if the PIN is unique
        if pin not in existing_pins:
            return pin


def generate_unique_account_number():
    while True:
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        existing_account_numbers = models.UserSecure.objects.values_list('user_id', flat=True)
        if account_number not in existing_account_numbers:
            return account_number


def unique_pin():
    exist = models.AuthenticationPin.objects.values_list('user_pin', flat=True)
    existing_pins = list(exist)
    return generate_unique_pin(existing_pins)

def hash_md5(password):
    return hashlib.md5(password.encode()).hexdigest()


def create_simple_jwt_session(user):
    refresh = RefreshToken.for_user(user)
        
    try:
        user_details = models.UserDetails.objects.filter(user=user).first()
        first_name = user_details.first_name if user_details else ""
        last_name = user_details.last_name if user_details else ""
    except:
        first_name, last_name = "", ""

    # Resolve business owner for managers/staff to get the correct store_setup
    owner = get_owner_from_user(user)

    # Get store setup status from the owner's BusinessDetails
    business = models.BusinessDetails.objects.filter(user=owner).first()
    store_setup = business.store_setup if business else False

    response = Response()
    response.data = {
        'status': True,
        'refresh': str(refresh),
        'jwt': str(refresh.access_token),
        'user': {
            'first_name': first_name,
            'last_name': last_name,
            'email': user.user_email,
            'store_setup': store_setup
        }
    }
    return response

def get_simple_jwt_id(token):
    auth_header = token.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token_str = auth_header.split(' ')[1]
    else:
        token_str = auth_header
    access_token = AccessToken(token_str)
    user_id = access_token.get('user_id')
    return user_id


def create_jwt_session(user_id) -> Response:
    try:
        secure_model = get_object_or_404(models.UserSecure, user_id=user_id)
        token, created = Token.objects.get_or_create(user=secure_model)

        response = Response()
        response.data = {
            'status': True,
            'jwt': token.key
        }
        return response
    except Exception as e:
        raise Exception(str(e))


def get_id(request):
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token_str = auth_header.split(' ')[1]
    else:
        token_str = auth_header
    
    if not token_str or token_str == "null":
        raise Exception("Authorization token is missing or null")

    try:
        access_token = AccessToken(token_str)
        user_id = access_token.get('user_id')
        
        request.actual_user_id = user_id
        
        from api.models import UserSecure
        user = UserSecure.objects.filter(user_id=user_id).first()
        if user and user.user_type in ['staff', 'manager']:
            if getattr(user, 'business_owner', None):
                return user.business_owner.user_id
            elif user.user_type == 'manager':
                from api.models import UserManagers
                manager_record = UserManagers.objects.filter(manager_email__iexact=user.user_email).first()
                if manager_record and manager_record.user:
                    return manager_record.user.user_id
        
        return user_id
    except Exception as e:
        raise Exception(f"Token validation error: {str(e)}")

def enforce_permissions(request, permission_field):
    """
    Checks if the actual user (manager or staff) has the given boolean permission.
    Returns True if permitted, False if denied.
    """
    from api.models import UserSecure
    actual_user = None
    if hasattr(request, 'actual_user_id'):
        actual_user = UserSecure.objects.filter(user_id=request.actual_user_id).first()
    elif hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
        actual_user = request.user
        
    if not actual_user or actual_user.user_type not in ['manager', 'staff']:
        return True
        
    if actual_user.user_type == 'manager':
        from api.models import UserManagers
        manager = UserManagers.objects.filter(manager_email__iexact=actual_user.user_email).first()
        if manager and not getattr(manager, permission_field, False):
            return False
            
    elif actual_user.user_type == 'staff':
        from api.models import UserPayroll
        staff = UserPayroll.objects.filter(user_id=actual_user).first()
        if staff and not getattr(staff, permission_field, False):
            return False
            
    return True

def get_owner_from_user(user):
    """
    Returns the business owner user if the given user is a manager or staff.
    Otherwise, returns the user themselves.
    """
    if user and user.user_type in ['manager', 'staff']:
        if getattr(user, 'business_owner', None):
            return user.business_owner
        
        # Fallback for managers without the direct business_owner FK
        if user.user_type == 'manager':
            from api.models import UserManagers
            manager_record = UserManagers.objects.filter(manager_email__iexact=user.user_email).first()
            if manager_record and manager_record.user:
                return manager_record.user
                
    return user