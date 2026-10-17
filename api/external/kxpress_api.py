import os
import requests
from django.conf import settings

class KxpressAPI:
    """
    Client for the Kxpress (Mercury) Delivery API.
    """
    BASE_URL = "https://my.kos.ng/api"

    def __init__(self):
        self.public_key = getattr(settings, 'KXPRESS_CLIENT_ID', os.environ.get('KXPRESS_CLIENT_ID'))
        self.secret_key = getattr(settings, 'KXPRESS_SECRET_KEY', os.environ.get('KXPRESS_SECRET_KEY'))
        
        if not self.public_key or not self.secret_key:
            # We will handle missing keys gracefully in views, but log a warning here if possible
            pass

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "public-key": str(self.public_key),
            "secret": str(self.secret_key)
        }

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, data=None):
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def get_states(self):
        """
        Fetch all Nigerian states.
        """
        return self._get('get-states')

    def get_lgas(self, state_id):
        """
        Fetch all LGAs for a given state.
        """
        return self._get('get-lgas', params={'state_id': state_id})

    def calculate_shipping(self, from_state, from_lga, to_state, to_lga, weight):
        """
        Calculate shipping fee.
        """
        payload = {
            "state": from_state,
            "fromLga": from_lga,
            "toState": to_state,
            "toLga": to_lga,
            "weight": weight
        }
        return self._post('calculate-weight', data=payload)

    def generate_waybill(self, payload):
        """
        Generate a waybill for an order.
        """
        return self._post('generate-waybill', data=payload)

    def track_order(self, order_no):
        """
        Track an order by its waybill number.
        """
        return self._get(f'track-order/{order_no}')
