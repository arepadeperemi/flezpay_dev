from rest_framework import serializers
from api import models



class UserSecureSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserSecure
        fields = ['user_email', 'user_phone', 'password', 'user_id', 'user_type']
        extra_kwargs = {
            'password': {"write_only": True}
        }

    def validate(self, data):
        if models.UserSecure.objects.filter(user_id=data['user_id']).exists():
            raise serializers.ValidationError({'user_id': 'Account creation error. Try again'})
        if models.UserSecure.objects.filter(user_phone=data['user_phone']).exists():
            raise serializers.ValidationError({'user_phone': 'This phone number exists with us already'})
        if not models.AuthenticationPin.objects.filter(user_pin=data['user_pin'], user_phone=data['user_phone']).exists():
            raise serializers.ValidationError({'user_pin': 'Provide a valid verification pin'})
        return data


class UserDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.UserDetails
        fields = ['first_name', 'last_name', 'user_country']