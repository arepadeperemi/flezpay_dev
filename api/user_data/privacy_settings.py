import traceback
import json
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from api import models
from api.functions import misc


class PrivacySettingsView(APIView):
    """Get and update user privacy settings"""

    def get(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            # Get privacy settings, ensure it's always a dict
            privacy_settings = instance.privacy_settings
            if privacy_settings is None:
                privacy_settings = {}
            elif isinstance(privacy_settings, str):
                # If it's a string, try to parse it as JSON
                try:
                    privacy_settings = json.loads(privacy_settings)
                except:
                    privacy_settings = {}
            elif not isinstance(privacy_settings, dict):
                privacy_settings = {}
            
            # Return default structure with current values
            return Response({
                'status': True,
                'settings': {
                    'data_sharing': privacy_settings.get('data_sharing', True),
                    'analytics': privacy_settings.get('analytics', True),
                    'marketing_communications': privacy_settings.get('marketing_communications', True),
                    'profile_visibility': privacy_settings.get('profile_visibility', 'public'),  # public, private, friends
                    'transaction_history_visibility': privacy_settings.get('transaction_history_visibility', 'private'),  # public, private
                    'two_factor_enabled': privacy_settings.get('two_factor_enabled', False),
                    'currency': privacy_settings.get('currency', 'NGN'),
                    'decimal_places': privacy_settings.get('decimal_places', '2'),
                    'notifications_sales': privacy_settings.get('notifications_sales', True),
                    'notifications_email': privacy_settings.get('notifications_email', True),
                    'notifications_stock': privacy_settings.get('notifications_stock', False),
                    'biometric_login': privacy_settings.get('biometric_login', False),
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error = str(e)
            if type(e).__name__ == "KeyError":
                error = f"{e} is required"
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            # Get current privacy settings and ensure it's a dict
            privacy_settings = instance.privacy_settings
            if privacy_settings is None:
                privacy_settings = {}
            elif isinstance(privacy_settings, str):
                # If it's a string, try to parse it as JSON
                try:
                    privacy_settings = json.loads(privacy_settings)
                except:
                    privacy_settings = {}
            elif not isinstance(privacy_settings, dict):
                privacy_settings = {}
            
            # Get settings from request data - ensure it's a dict
            # Handle both request.data (DRF) and request.POST (Django)
            if hasattr(request, 'data'):
                raw_data = request.data
            else:
                raw_data = request.POST
            
            # Ensure we have a dict-like object
            if not isinstance(raw_data, dict):
                raw_data = dict(raw_data) if hasattr(raw_data, 'items') else {}
            
            settings_to_update = raw_data.get('settings', {})
            
            # Handle the case where settings_to_update might be a string representation
            # This can happen when using MultipartRequest which converts dicts to strings
            if isinstance(settings_to_update, str):
                # Try to parse as JSON first (handles proper JSON strings from jsonEncode)
                try:
                    settings_to_update = json.loads(settings_to_update)
                except (json.JSONDecodeError, ValueError):
                    # If JSON parsing fails, it might be a Python dict string representation
                    # This handles cases like "{'key': 'value'}" from toString()
                    try:
                        # Replace single quotes with double quotes for JSON compatibility
                        # But be careful with boolean values - Python uses True/False, JSON uses true/false
                        settings_str = settings_to_update.replace("'", '"')
                        settings_str = settings_str.replace('True', 'true').replace('False', 'false')
                        settings_to_update = json.loads(settings_str)
                    except:
                        settings_to_update = {}
            elif not isinstance(settings_to_update, dict):
                settings_to_update = {}
            
            # Validate and update each setting - use .get() for safe access
            if isinstance(settings_to_update, dict) and 'data_sharing' in settings_to_update:
                privacy_settings['data_sharing'] = bool(settings_to_update.get('data_sharing', False))
            
            if isinstance(settings_to_update, dict) and 'analytics' in settings_to_update:
                privacy_settings['analytics'] = bool(settings_to_update.get('analytics', False))
            
            if isinstance(settings_to_update, dict) and 'marketing_communications' in settings_to_update:
                privacy_settings['marketing_communications'] = bool(settings_to_update.get('marketing_communications', False))
            
            if isinstance(settings_to_update, dict) and 'profile_visibility' in settings_to_update:
                visibility = settings_to_update.get('profile_visibility')
                if isinstance(visibility, str) and visibility in ['public', 'private', 'friends']:
                    privacy_settings['profile_visibility'] = visibility
            
            if isinstance(settings_to_update, dict) and 'transaction_history_visibility' in settings_to_update:
                visibility = settings_to_update.get('transaction_history_visibility')
                if isinstance(visibility, str) and visibility in ['public', 'private']:
                    privacy_settings['transaction_history_visibility'] = visibility
            
            if isinstance(settings_to_update, dict) and 'two_factor_enabled' in settings_to_update:
                privacy_settings['two_factor_enabled'] = bool(settings_to_update.get('two_factor_enabled', False))
            
            if isinstance(settings_to_update, dict) and 'currency' in settings_to_update:
                privacy_settings['currency'] = str(settings_to_update.get('currency', 'NGN'))
                
            if isinstance(settings_to_update, dict) and 'decimal_places' in settings_to_update:
                privacy_settings['decimal_places'] = str(settings_to_update.get('decimal_places', '2'))
                
            if isinstance(settings_to_update, dict) and 'notifications_sales' in settings_to_update:
                privacy_settings['notifications_sales'] = bool(settings_to_update.get('notifications_sales', True))
                
            if isinstance(settings_to_update, dict) and 'notifications_email' in settings_to_update:
                privacy_settings['notifications_email'] = bool(settings_to_update.get('notifications_email', True))
                
            if isinstance(settings_to_update, dict) and 'notifications_stock' in settings_to_update:
                privacy_settings['notifications_stock'] = bool(settings_to_update.get('notifications_stock', False))

            if isinstance(settings_to_update, dict) and 'biometric_login' in settings_to_update:
                privacy_settings['biometric_login'] = bool(settings_to_update.get('biometric_login', False))
            
            # Save the updated settings
            instance.privacy_settings = privacy_settings
            instance.save(update_fields=['privacy_settings'])
            
            # Refresh from database to get the updated value
            instance.refresh_from_db()
            
            # Ensure the returned value is a dict
            final_settings = instance.privacy_settings
            if not isinstance(final_settings, dict):
                if isinstance(final_settings, str):
                    try:
                        final_settings = json.loads(final_settings)
                    except:
                        final_settings = {}
                else:
                    final_settings = {}
            
            return Response({
                'status': True,
                'message': 'Privacy settings updated successfully',
                'settings': final_settings
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error = str(e)
            error_type = type(e).__name__
            if error_type == "KeyError":
                error = f"{e} is required"
            elif error_type == "TypeError":
                error = f"Type error: {error}. This might be due to incorrect data format."
            return Response({
                'status': False,
                'message': error,
                'error_type': error_type,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class LoginActivityView(APIView):
    """Get user login activity history"""

    def get(self, request):
        try:
            user_id = misc.get_id(request)
            instance = models.UserSecure.objects.get(user_id=user_id)
            
            # Get login notifications (notification_type='auth' with 'login' in description)
            login_notifications = models.Notifications.objects.filter(
                user=instance,
                notification_type='auth'
            ).filter(
                description__icontains='logged into'
            ).order_by('-id')[:20]  # Get last 20 login activities
            
            activities = []
            for notification in login_notifications:
                # Get timestamp from notification
                date_str = None
                if hasattr(notification, 'timestamp') and notification.timestamp:
                    try:
                        from django.utils import timezone
                        # Format the datetime
                        date_str = notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        date_str = str(notification.timestamp) if hasattr(notification, 'timestamp') else None
                
                # Extract location from description
                location = 'Unknown'
                description = notification.description or ''
                # Format: "You logged into your account from [Location]. If this wasn't you..."
                if 'from' in description.lower():
                    parts = description.split('from')
                    if len(parts) > 1:
                        location_part = parts[-1].split('.')[0].strip()  # Get location before the period
                        location = location_part if location_part else 'Unknown'
                
                activities.append({
                    'date': date_str,
                    'location': location,
                })
            
            return Response({
                'status': True,
                'activities': activities
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            error = str(e)
            return Response({
                'status': False,
                'message': error,
                'traceback': traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)

