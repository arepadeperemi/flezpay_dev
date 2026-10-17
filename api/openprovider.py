import os
import requests
import re
from django.conf import settings
from dotenv import load_dotenv

ALLOWED_EXTENSIONS = ['com', 'net', 'org', 'store', 'online', 'co', 'io', 'biz']

def validate_domain_format(domain_name, extension):
    if not domain_name or not extension:
        return False, "Domain name and extension are required."
    domain_name = domain_name.strip().lower()
    extension = extension.strip().lower()
    if not re.match(r'^[a-z0-9-]+$', domain_name):
        return False, "Invalid characters in domain name."
    if domain_name.startswith('-') or domain_name.endswith('-'):
        return False, "Domain name cannot start or end with a hyphen."
    if extension not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    return True, ""

class OpenproviderAPI:
    BASE_URL = 'https://api.openprovider.eu/v1beta'
    
    def __init__(self):
        load_dotenv()
        self.username = os.getenv('OP_USERNAME')
        self.password = os.getenv('OP_PASSWORD')
        self.token = None
        
    def authenticate(self):
        login_data = {
            "username": self.username,
            "password": self.password
        }
        try:
            response = requests.post(f"{self.BASE_URL}/auth/login", json=login_data, timeout=10)
            if response.status_code == 200:
                data = response.json().get('data', {})
                self.token = data.get('token')
                return True
            return False
        except Exception:
            return False

    def check_domain(self, domain_name, extension, suggest=True):
        is_valid, err_msg = validate_domain_format(domain_name, extension)
        if not is_valid:
            return {"status": "error", "message": err_msg}
            
        if not self.token and not self.authenticate():
            return {"status": "error", "message": f"Failed to authenticate with provider."}
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        extensions_to_check = [extension]
        if suggest:
            popular_extensions = ['com', 'net', 'org', 'store', 'online', 'co', 'io', 'biz']
            for ext in popular_extensions:
                if ext != extension:
                    extensions_to_check.append(ext)
        
        domains_payload = [{"name": domain_name, "extension": ext} for ext in extensions_to_check]
        
        check_data = {
            "domains": domains_payload,
            "with_price": True
        }
        
        try:
            response = requests.post(f"{self.BASE_URL}/domains/check", json=check_data, headers=headers, timeout=15)
            if response.status_code == 200:
                data_obj = response.json().get('data', {})
                results = data_obj.get('results', [])
                if results:
                    # Find primary result
                    primary_item = next((item for item in results if item.get('domain', '').split('.')[-1] == extension), results[0])
                    status = primary_item.get('status', '') # "free", "active"
                    premium = primary_item.get('is_premium', False)
                    price_info = primary_item.get('price', {}).get('product', {})
                    price = float(price_info.get('price', 0))
                    currency = price_info.get('currency', 'USD')
                    
                    suggestions = []
                    for item in results:
                        domain_str = item.get('domain', '')
                        ext = domain_str.split('.')[-1] if '.' in domain_str else ''
                        if ext != extension and item.get('status') == 'free':
                            s_price_info = item.get('price', {}).get('product', {})
                            suggestions.append({
                                "domain": domain_str,
                                "extension": ext,
                                "price": float(s_price_info.get('price', 0)),
                                "currency": s_price_info.get('currency', 'USD'),
                                "premium": item.get('is_premium', False)
                            })
                    
                    return {
                        "status": "success",
                        "domain": f"{domain_name}.{extension}",
                        "availability": status,
                        "premium": premium,
                        "price": price,
                        "currency": currency,
                        "suggestions": suggestions
                    }
            return {"status": "error", "message": response.json().get('desc', 'Unknown error')}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def transfer_domain(self, domain_name, extension, auth_code):
        is_valid, err_msg = validate_domain_format(domain_name, extension)
        if not is_valid:
            return {"status": "error", "message": err_msg}
            
        if not self.token and not self.authenticate():
            return {"status": "error", "message": "Failed to authenticate with provider."}
            
        headers = {"Authorization": f"Bearer {self.token}"}
        handle_id = os.getenv('OP_BILLING_HANDLE')
        payload = {
            "domain": {
                "name": domain_name,
                "extension": extension
            },
            "auth_code": auth_code,
            "autorenew": "on",
            "owner_handle": handle_id,
            "admin_handle": handle_id,
            "tech_handle": handle_id,
            "billing_handle": handle_id
        }
        
        try:
            response = requests.post(f"{self.BASE_URL}/domains/transfer", json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                return {"status": "success", "message": "Domain transfer initiated successfully."}
            desc = response.json().get('desc', 'Failed to transfer domain.')
            if 'failed_auth_code' in desc or 'auth_code' in desc.lower() or 'authorization' in desc.lower():
                desc = "The Authorization/EPP code is invalid or the transfer lock is active. Please ensure you have disabled the transfer lock at your current registrar and entered the correct EPP code."
            return {"status": "error", "message": desc}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def register_domain(self, domain_name, extension, user_data=None):
        is_valid, err_msg = validate_domain_format(domain_name, extension)
        if not is_valid:
            return {"status": "error", "message": err_msg}
            
        if not self.token and not self.authenticate():
            return {"status": "error", "message": "Failed to authenticate with provider."}
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        handle_id = os.getenv('OP_BILLING_HANDLE')
        payload = {
            "domain": {
                "name": domain_name,
                "extension": extension
            },
            "period": 1,
            "owner_handle": handle_id,
            "admin_handle": handle_id,
            "tech_handle": handle_id,
            "billing_handle": handle_id
        }
        
        try:
            response = requests.post(f"{self.BASE_URL}/domains", json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                return {"status": "success", "message": "Domain registered successfully."}
            return {"status": "error", "message": response.json().get('desc', 'Failed to register domain.')}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def create_dns_zone(self, domain_name, extension, ip_address):
        if not self.token and not self.authenticate():
            return {"status": "error", "message": "Failed to authenticate with provider."}
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        payload = {
            "domain": {
                "name": domain_name,
                "extension": extension
            },
            "type": "master",
            "records": [
                {
                    "ttl": 900,
                    "type": "A",
                    "value": ip_address
                },
                {
                    "name": "www",
                    "ttl": 900,
                    "type": "A",
                    "value": ip_address
                }
            ]
        }
        
        try:
            response = requests.post(f"{self.BASE_URL}/dns/zones", json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                return {"status": "success", "message": "DNS zone created successfully."}
            return {"status": "error", "message": response.json().get('desc', 'Failed to create DNS zone.')}
        except Exception as e:
            return {"status": "error", "message": str(e)}
