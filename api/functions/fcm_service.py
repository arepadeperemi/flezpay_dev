"""
Firebase Cloud Messaging service for sending push notifications

Configuration details from firebase_options.dart:
- Project ID: flezpay-35053
- Messaging Sender ID: 816215692162
- Storage Bucket: flezpay-35053.firebasestorage.app
"""
import os

from pathlib import Path
from typing import List, Dict, Optional
from django.conf import settings



try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    pass


def initialize_firebase():
    """Initialize Firebase Admin SDK
    
    Uses configuration from firebase_options.dart:
    - Project ID: flezpay-35053
    - Messaging Sender ID: 816215692162
    
    Requires Firebase service account JSON file for authentication.
    """
    if not FIREBASE_AVAILABLE:
        return False
    
    try:
        # Check if Firebase is already initialized
        if firebase_admin._apps:
            pass
            return True
        
        # Try to get Firebase credentials from environment or settings
        # Option 1: Service account JSON file path (recommended)
        service_account_path = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_PATH', None)
        if service_account_path:
            # Handle both string paths and Path objects
            if isinstance(service_account_path, str):
                service_account_path = Path(service_account_path)
            elif hasattr(service_account_path, '__fspath__'):
                service_account_path = Path(service_account_path)
            
            if service_account_path.exists():
                try:
                    cred = credentials.Certificate(str(service_account_path))
                    # Optionally set project ID from settings
                    project_id = getattr(settings, 'FIREBASE_PROJECT_ID', None)
                    if project_id:
                        firebase_admin.initialize_app(cred, {'projectId': project_id})
                    else:
                        firebase_admin.initialize_app(cred)
                    pass
                    return True
                except Exception as e:
                    pass
            else:
                pass
        
        # Option 2: Service account JSON as dict (from environment variable)
        service_account_dict = getattr(settings, 'FIREBASE_SERVICE_ACCOUNT_DICT', None)
        if service_account_dict:
            try:
                cred = credentials.Certificate(service_account_dict)
                project_id = getattr(settings, 'FIREBASE_PROJECT_ID', None)
                if project_id:
                    firebase_admin.initialize_app(cred, {'projectId': project_id})
                else:
                    firebase_admin.initialize_app(cred)
                pass
                return True
            except Exception as e:
                pass
        
        # Option 3: Default credentials (for Google Cloud environments)
        try:
            project_id = getattr(settings, 'FIREBASE_PROJECT_ID', None)
            if project_id:
                firebase_admin.initialize_app(options={'projectId': project_id})
            else:
                firebase_admin.initialize_app()
            pass
            return True
        except Exception as e:
            pass
        
        pass
        return False
    except Exception as e:
        pass
        return False


def send_fcm_notification(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict] = None,
    image_url: Optional[str] = None
) -> Dict[str, any]:
    """
    Send FCM notification to multiple device tokens
    
    Args:
        tokens: List of FCM device tokens
        title: Notification title
        body: Notification body
        data: Optional data payload (dict)
        image_url: Optional image URL for notification
    
    Returns:
        Dict with success_count, failure_count, and results
    """
    if not FIREBASE_AVAILABLE:
        pass
        return {
            'success_count': 0,
            'failure_count': len(tokens),
            'results': []
        }
    
    if not initialize_firebase():
        pass
        return {
            'success_count': 0,
            'failure_count': len(tokens),
            'results': []
        }
    
    if not tokens:
        return {
            'success_count': 0,
            'failure_count': 0,
            'results': []
        }
    
    try:
        # Create notification payload
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url
        )
        
        # Create Android config with proper notification channel
        android_config = messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                sound='default',
                channel_id='flezpay_notifications',
                priority='high',
                visibility='public',
                click_action='FLUTTER_NOTIFICATION_CLICK',
                tag='flezpay_notification'
            )
        )
        
        # Create APNS config for iOS with proper settings
        apns_config = messaging.APNSConfig(
            headers={
                'apns-priority': '10',  # High priority
            },
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound='default',
                    badge=None,
                    content_available=True,
                    alert=messaging.ApsAlert(
                        title=title,
                        body=body
                    ),
                    category='flezpay_notification'
                )
            )
        )
        
        # Create message
        message = messaging.MulticastMessage(
            notification=notification,
            data=data or {},
            android=android_config,
            apns=apns_config,
            tokens=tokens
        )
        
        # Send the message
        response = messaging.send_each_for_multicast(message)
        
        # Process results
        success_count = response.success_count
        failure_count = response.failure_count
        results = []
        
        for idx, result in enumerate(response.responses):
            token = tokens[idx]
            if result.success:
                results.append({
                    'token': token,
                    'success': True
                })
            else:
                results.append({
                    'token': token,
                    'success': False,
                    'error': str(result.exception) if result.exception else 'Unknown error'
                })
                pass
        
        return {
            'success_count': success_count,
            'failure_count': failure_count,
            'results': results
        }
    
    except Exception as e:
        pass
        return {
            'success_count': 0,
            'failure_count': len(tokens),
            'results': [],
            'error': str(e)
        }


def send_fcm_to_user(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict] = None,
    image_url: Optional[str] = None
) -> Dict[str, any]:
    """
    Send FCM notification to all active devices of a user
    
    Args:
        user_id: User ID
        title: Notification title
        body: Notification body
        data: Optional data payload
        image_url: Optional image URL
    
    Returns:
        Dict with success_count, failure_count, and results
    """
    from api.models import FCMDeviceToken, UserSecure
    
    try:
        # First verify user exists
        try:
            user = UserSecure.objects.get(user_id=user_id)
        except UserSecure.DoesNotExist:
            pass
            return {
                'success_count': 0,
                'failure_count': 0,
                'results': [],
                'message': f'User {user_id} not found'
            }
        
        # Get all active tokens for the user
        tokens = list(
            FCMDeviceToken.objects.filter(
                user=user,
                is_active=True
            ).values_list('token', flat=True)
        )
        
        pass
        
        if not tokens:
            pass
            return {
                'success_count': 0,
                'failure_count': 0,
                'results': [],
                'message': 'No active device tokens found. User needs to log in and register FCM token.'
            }
        
        pass
        result = send_fcm_notification(
            tokens=tokens,
            title=title,
            body=body,
            data=data,
            image_url=image_url
        )
        return result
    
    except Exception as e:
        pass
        return {
            'success_count': 0,
            'failure_count': 0,
            'results': [],
            'error': str(e)
        }

