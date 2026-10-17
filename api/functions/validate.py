from api import models


def validate_auth_pin(pin, phone):
    pins = models.AuthenticationPin.objects.filter(user_pin=pin, user_phone=phone)
    if not pins.exists():
        raise Exception('Pin is invalid')