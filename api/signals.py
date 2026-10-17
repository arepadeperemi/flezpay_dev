from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import (
    UserSecure, 
    UserTransactions as Transaction, 
    UserItems, UserCartItems,
    UserWithdrawalAccounts, BankDepositDetails, Notifications,
    CryptoAssets, CryptoAssetChains
)
import json



def send_user_data_update(user_id):
    """Helper function to send updated user data."""
    try:
        from api.user_data.data_views import user_data_db
        channel_layer = get_channel_layer()
        if channel_layer is None:
            pass
            return
        
        group_name = f"user_{user_id}_data"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_updated_user_data",
                "data": user_data_db(user_id)
            }
        )
        pass
    except Exception:
        pass


def send_user_logout_signal(user_id):
    """Helper function to send logout signal to user via WebSocket."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            pass
            return
            
        group_name = f"user_{user_id}_data"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_logout_signal",
                "message": "Your account has been deactivated. Please contact support for assistance."
            }
        )
        pass
    except Exception:
        pass
 


@receiver(post_save, sender=UserSecure)
@receiver(post_delete, sender=UserSecure)
def send_user_update(sender, instance, **kwargs):
    send_user_data_update(instance.user_id)


@receiver(post_save, sender=UserItems)
@receiver(post_delete, sender=UserItems)
def send_user_items_update(sender, instance, **kwargs):
    send_user_data_update(instance.user.user_id)

    # Update any user who has the item in their cart
    related_cart_items = UserCartItems.objects.filter(item_id=str(instance.item_id))
    for cart_item in related_cart_items:
        send_user_data_update(cart_item.user.user_id)

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def send_transaction_update(sender, instance, **kwargs):
    """Send websocket update when a transaction is created, updated, or deleted."""
    try:
        # Ensure user relationship is loaded
        if hasattr(instance, 'user') and instance.user is not None:
            # Try to get user_id from the foreign key directly if user object isn't loaded
            user_id = getattr(instance, 'user_id', None)
            if user_id:
                pass
                send_user_data_update(user_id)
            else:
                pass
        
    except Exception as e:
        pass


@receiver(post_delete, sender=UserCartItems)
@receiver(post_save, sender=UserCartItems)
def send_cart_item_update(sender, instance, **kwargs):
    send_user_data_update(instance.user.user_id)


@receiver(post_delete, sender=UserWithdrawalAccounts)
@receiver(post_save, sender=UserWithdrawalAccounts)
def send_colection_add(sender, instance, **kwargs):
    send_user_data_update(instance.withdrawal_unique)  

@receiver(post_delete, sender=BankDepositDetails)
@receiver(post_save, sender=BankDepositDetails)
def send_colection_add(sender, instance, **kwargs):
    send_user_data_update(instance.user)

@receiver(post_delete, sender=Notifications)
@receiver(post_save, sender=Notifications)
def send_colection_add(sender, instance, **kwargs):
    send_user_data_update(instance.user)


# Global change
User = UserSecure

@receiver(post_save, sender=CryptoAssets)
@receiver(post_delete, sender=CryptoAssets)
def send_crypto_asset_update(sender, instance, **kwargs):
    for user in User.objects.all():
        send_user_data_update(user.user_id)

@receiver(post_save, sender=CryptoAssetChains)
@receiver(post_delete, sender=CryptoAssetChains)
def send_crypto_chain_update(sender, instance, **kwargs):
    for user in User.objects.all():
        send_user_data_update(user.user_id)


# =============================
# GLOBAL CRYPTO ASSET UPDATES
# =============================

@receiver([post_save, post_delete], sender=CryptoAssets)
def send_crypto_asset_update(sender, instance, **kwargs):
    """When a crypto asset is created, updated, or deleted, update every user."""
    for user in UserSecure.objects.all():
        send_user_data_update(user.user_id)


@receiver([post_save, post_delete], sender=CryptoAssetChains)
def send_crypto_chain_update(sender, instance, **kwargs):
    """When a crypto chain is created, updated, or deleted, update every user."""
    for user in UserSecure.objects.all():
        send_user_data_update(user.user_id)