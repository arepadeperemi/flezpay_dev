from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import transaction
from api.models import UserSecure, UserDetails, UserTrxPin
from api.functions import misc

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        
        with transaction.atomic():
            # Check if UserDetails already exists (in case save_user was called on an existing user)
            if not getattr(user, 'user_id', None):
                user.user_id = misc.generate_unique_account_number()
                user.user_type = 'business'
                user.is_verified = True
                user.save()
                
            if not UserDetails.objects.filter(user=user).exists():
                # Extract names from sociallogin
                first_name = sociallogin.account.extra_data.get('given_name', '')
                last_name = sociallogin.account.extra_data.get('family_name', '')
                
                UserDetails.objects.create(
                    user=user,
                    user_country="NG",
                    first_name=first_name,
                    last_name=last_name
                )
                
            if not UserTrxPin.objects.filter(user_details=user).exists():
                # Create default trx pin
                UserTrxPin.objects.create(
                    user_details=user,
                    account_pin=misc.hash_md5(misc.hash_md5("000000"))
                )
                
        return user
