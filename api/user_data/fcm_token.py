"""
FCM Token management endpoints
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from api import models
from api.functions import misc
from api.functions import misc
from django.db import transaction




class RegisterFCMToken(APIView):
    """Register or update FCM device token for a user"""
    
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            token = request.data.get('token')
            device_type = request.data.get('device_type', 'android')  # android, ios, web
            device_id = request.data.get('device_id', '')
            
            if not token:
                return Response({
                    'status': False,
                    'message': 'FCM token is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if device_type not in ['android', 'ios', 'web']:
                device_type = 'android'
            
            try:
                user = models.UserSecure.objects.get(user_id=user_id)
            except models.UserSecure.DoesNotExist:
                return Response({
                    'status': False,
                    'message': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get or create FCM token
            fcm_token, created = models.FCMDeviceToken.objects.get_or_create(
                user=user,
                token=token,
                defaults={
                    'device_type': device_type,
                    'device_id': device_id,
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing token
                fcm_token.device_type = device_type
                fcm_token.device_id = device_id
                fcm_token.is_active = True
                fcm_token.save()
            
            return Response({
                'status': True,
                'message': 'FCM token registered successfully',
                'created': created
            })
            
        except Exception as e:
            pass
            return Response({
                'status': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UnregisterFCMToken(APIView):
    """Unregister FCM device token (mark as inactive)"""
    
    def post(self, request):
        try:
            user_id = misc.get_id(request)
            token = request.data.get('token')
            
            if not token:
                return Response({
                    'status': False,
                    'message': 'FCM token is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                fcm_token = models.FCMDeviceToken.objects.get(
                    user__user_id=user_id,
                    token=token
                )
                fcm_token.is_active = False
                fcm_token.save()
                
                return Response({
                    'status': True,
                    'message': 'FCM token unregistered successfully'
                })
            except models.FCMDeviceToken.DoesNotExist:
                return Response({
                    'status': False,
                    'message': 'FCM token not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            pass
            return Response({
                'status': False,
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

