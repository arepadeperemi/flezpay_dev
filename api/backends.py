from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import UserSecure

class FlezAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None
        
        try:
            # Check if username is an email or phone number
            # We check isdigit() to avoid passing non-numeric strings to the BigIntegerField user_phone
            if username.isdigit():
                user = UserSecure.objects.filter(Q(user_email=username) | Q(user_phone=username)).first()
            else:
                user = UserSecure.objects.filter(user_email=username).first()
            
            if user and user.check_password(password):
                return user
        except Exception:
            return None

    def get_user(self, user_id):
        try:
            return UserSecure.objects.get(pk=user_id)
        except UserSecure.DoesNotExist:
            return None
