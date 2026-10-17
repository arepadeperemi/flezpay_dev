import json

from dotenv import load_dotenv
from requests import RequestException
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
import traceback
import uuid
import time
import hashlib
from datetime import datetime
from uuid_extensions import uuid7, uuid7str
import requests
import os

load_dotenv()

class PSB:

    def __init__(self):
        self.base_url = "https://baastest.9psb.com.ng/iva-api/v1/merchant/virtualaccount"
        self.private_key = os.getenv('PSB_PRIVATE_KEY')
        self.public_key = os.getenv('PSB_PUBLIC_KEY')
        self.webhook_password = os.getenv("PSB_WEBHOOK_PASSWORD")
        self.beneficiary_account_number = os.getenv('PSB_BAN')
        self.beneficiary_bank_code = os.getenv('PSB_BBC')

    def __trx_reference(self, prefix="TXN", max_length=35):
        if max_length < 10:
            raise ValueError("Max length must be at least 10 characters")

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        unique_id = uuid.uuid4().hex

        combined = f"{prefix}{timestamp}{unique_id}"

        hash_obj = hashlib.sha256(combined.encode())
        hex_digest = hash_obj.hexdigest()

        available_length = max_length - len(prefix)
        reference = prefix + hex_digest[:available_length]

        return reference

    def sha512_hash(self, data):
        if isinstance(data, str):
            data = data.encode()
        hash_object = hashlib.sha512(data)
        hex_digest = hash_object.hexdigest()

        return hex_digest

    def set_headers(self, token) -> dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {token}"
        }

    def authenticate(self):
        try:
            url = f"{self.base_url}/authenticate"
            payload = {
                'publickey': self.public_key,
                'privatekey': self.private_key
            }
            response = requests.post(url, payload)
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data['access_token'] is None:
                    raise Exception(f"Authentication error: {data['message']}")
                return data['access_token']
        except (Exception, RequestException) as e:
            raise Exception(str(e))



    def create_virtual_account(self, account_name):
        try:
            url = f"{self.base_url}/create"
            payload = {
                'transaction': {'reference': self.__trx_reference()},
                'order': {
                    'currency': "NGN",
                    'description': 'Virtual account',
                    'country': 'NG',
                    'amounttype': 'ANY',
                },
                'customer': {
                    'account': {
                        'name': account_name,
                        'type': "STATIC"
                    }
                },
                'beneficiarytocredit': {
                    'accountnumber': self.beneficiary_account_number,
                    'bankcode': self.beneficiary_bank_code
                }
            }

            response = requests.post(url, data=json.dumps(payload), headers=self.set_headers(self.authenticate()))
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data['code'] != "00":
                    raise Exception(f"Error creating account: {data['message']}")
                return data
        except (Exception, RequestException) as e:
            raise Exception(str(e))


    def deactivate_virtual_account(self, reference, account_number):
        try:
            url = f"{self.base_url}/deactivate"
            payload = {
                'transaction': {'reference': reference},
                'customer': {
                    'account': {
                        'number': account_number,
                    }
                }
            }
            payload = json.dumps(payload)
            response = requests.post(url, data=payload, headers=self.set_headers(self.authenticate()))
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data['code'] != "00":
                    raise Exception(f"Error deactivating account: {data['message']}")
                return data
        except (Exception, RequestException) as e:
            raise Exception(str(e))


    def reactivate_virtual_account(self, reference, account_number):
        try:
            url = f"{self.base_url}/reactivate"
            payload = {
                'transaction': {'reference': reference},
                'customer': {
                    'account': {
                        'number': account_number,
                    }
                }
            }
            payload = json.dumps(payload)
            response = requests.post(url, data=payload, headers=self.set_headers(self.authenticate()))
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data['code'] != "00":
                    raise Exception(f"Error reactivating account: {data['message']}")
                return data
        except (Exception, RequestException) as e:
            raise Exception(str(e))


    def confirm_payment(self, reference, account_number, session_id=None, amount=None):
        try:
            url = f"{self.base_url}/confirmpayment"
            payload = {
                'reference': reference,
                'accountnumber': account_number
            }
            if session_id is not None:
                payload.update({'sessionid': session_id})
            if amount is not None:
                payload.update({'amount': amount})

            payload = json.dumps(payload)
            response = requests.post(url, data=payload, headers=self.set_headers(self.authenticate()))
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data['code'] != "00":
                    raise Exception(f"Error confirming payment: {data['message']}")
                return data
        except RequestException:
            return {
                'code': '99',
                'message': 'Error processing request'
            }


    def refund_virtual_account_payment(self, account_number, session_id, amount, date_of_submission):
        try:
            url = f"{self.base_url}/paymentrefund"
            hash_str = f"{self.private_key} + {session_id} + {account_number} + {amount} + {date_of_submission}"
            payload = {
                'sessionid': session_id,
                'hash': self.sha512_hash(hash_str),
                'amount': amount,
                'accountnumber': account_number
            }

            payload = json.dumps(payload)
            response = requests.post(url, data=payload, headers=self.set_headers(self.authenticate()))
            if response.status_code == 200 or response.status_code == 201:
                data = response.json()
                if data['code'] != "00":
                    raise Exception(f"Error confirming payment: {data['message']}")
                return data
        except (Exception, RequestException) as e:
            raise Exception(str(e))


    def webhook_response(self, request, virtual_account_number):
        if request['code'] == "00":
            try:
                sender_account_number = request['customer']['account']['senderaccountnumber']
                sender_bank_code = request['customer']['account']['senderbankcode']
                amount = request['order']['amount']
                session_id = request['transaction']['sessionid']
                reference_id = request['transaction']['reference']
            except KeyError as e:
                return {'code': '99', 'message': f'missing parameters: {str(e)}'}

            hash_str = f"{self.webhook_password} + {sender_account_number} + {sender_bank_code} + {virtual_account_number} + {amount}"

            if request['hash'] != self.sha512_hash(hash_str):
                return {'code': "47", 'message': 'Invalid transaction request'}

            return {
                'code': '00',
                'payment': self.confirm_payment(reference_id, virtual_account_number, session_id, amount),
                'data': request.data
            }
        else:
            return {
                'code': request.get('code', '99'),
                'message': request.get('message', 'Unknown error')
            }


if __name__ == '__main__':
    try:
        psb = PSB()
        v_account = "5032030094"
        ref = "TXNb0118e665bd33071c566825840d7f78f"

        print(psb.create_virtual_account())
    except Exception as e:
        print(str(e))