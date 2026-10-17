import requests
import hashlib
import hmac
from dotenv import load_dotenv
import os

load_dotenv()

class PaystackAPI:
    BASE_URL = "https://api.paystack.co"

    def __init__(self):
        # Force reload .env to ensure we pick up changes without a full server restart
        load_dotenv(override=True)
        self.secret_key = os.getenv("PAYSTACK_PRIVATE_KEY")
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }

    # ---------------- Customers ----------------
    def create_customer(self, email: str, first_name: str, last_name: str, phone: str):
        url = f"{self.BASE_URL}/customer"
        data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def create_dedicated_account(self, customer_id: int, preferred_bank: str = None):
        url = f"{self.BASE_URL}/dedicated_account"
        data = {
            "customer": customer_id,
            "preferred_bank": preferred_bank or "titan-paystack"
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    # ---------------- Transfers ----------------
    def create_transfer_recipient(self, name: str, account_number: str, bank_code: str, currency: str = "NGN"):
        url = f"{self.BASE_URL}/transferrecipient"
        data = {
            "type": "nuban",
            "name": name,
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": currency
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def initiate_transfer(self, amount: int, recipient_code: str, reference: str, reason: str = "", source: str = "balance"):
        url = f"{self.BASE_URL}/transfer"
        data = {
            "source": source,
            "amount": amount,
            "recipient": recipient_code,
            "reference": reference,
            "reason": reason
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    def bulk_transfer(self, transfers: list, source: str = "balance", currency: str = "NGN"):
        url = f"{self.BASE_URL}/transfer/bulk"
        data = {
            "currency": currency,
            "source": source,
            "transfers": transfers
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.json()

    # ---------------- Verification ----------------
    def resolve_account_number(self, account_number: str, bank_code: str):
        """
        Resolve account number using Paystack API.
        Returns account details if valid.
        """
            
        url = f"{self.BASE_URL}/bank/resolve"
        params = {
            "account_number": account_number,
            "bank_code": bank_code
        }
        response = requests.get(url, headers=self.headers, params=params, timeout=10)
        return response.json()

    # ---------------- Webhooks ----------------
    def verify_webhook(self, raw_body: bytes, signature: str) -> bool:
        """
        Verify Paystack webhook signature.
        """
        computed_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            raw_body,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature or "")
        
    def verify_transaction(self, reference: str) -> dict:
        """
        Verify a transaction by its reference.
        """
        url = f"{self.BASE_URL}/transaction/verify/{reference}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json()
        except requests.RequestException:
            return {"status": False, "message": "API request failed"}
