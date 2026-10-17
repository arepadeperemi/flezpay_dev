"""
Myaza Trust KYC Verification Client
API Reference: https://trust.myaza.co/documentation/introduction
"""

import requests
import logging
import hmac
import hashlib
import uuid
from django.conf import settings

logger = logging.getLogger(__name__)


class MyazaTrustAPI:
    """
    Client for Myaza Trust KYC verification service.
    Handles configuration, media uploads, verification requests,
    status polling, and webhook verification.
    """

    ID_TYPE_MAPPING = {
        'nin': 'nin',
        'national id (nin)': 'nin',
        'national id': 'nin',
        'national identification number (nin)': 'nin',
        'bvn': 'bvn',
        'bank verification number (bvn)': 'bvn',
        'bank verification number': 'bvn',
        'vnin': 'vnin',
        'virtual nin (vnin)': 'vnin',
        'virtual nin': 'vnin',
        'driver\'s license': 'drivers-license',
        'drivers license': 'drivers-license',
        'drivers-license': 'drivers-license',
        'driver licence': 'drivers-license',
        'driver_licence': 'drivers-license',
        'international passport': 'passport',
        'passport': 'passport',
        'voter\'s card': 'pvc',
        'voters card': 'pvc',
        'pvc': 'pvc',
        'permanent voter\'s card (pvc)': 'pvc',
        'tax id': 'tax-id',
        'tax identification number (tax id)': 'tax-id',
        'tax-id': 'tax-id',
    }

    def __init__(self, secret_key=None, publishable_key=None, base_url=None):
        self.secret_key = secret_key or getattr(settings, 'MYAZA_SECRET', '')
        self.publishable_key = publishable_key or getattr(settings, 'MYAZA_PUBLISHABLE', '')
        self.base_url = (base_url or getattr(settings, 'MYAZA_BASE_URL', 'https://trust.myaza.app/api/kyc')).rstrip('/')

    @classmethod
    def normalize_id_type(cls, raw_type):
        """Map human or legacy ID type strings to Myaza idType codes."""
        if not raw_type:
            return 'nin'
        cleaned = str(raw_type).strip().lower()
        return cls.ID_TYPE_MAPPING.get(cleaned, cleaned)

    def _get_auth_header(self, use_secret=False):
        key = self.secret_key if use_secret else (self.publishable_key or self.secret_key)
        return {'Authorization': f'Bearer {key}'}

    def get_config(self):
        """Fetch supported countries, ID types, and feature configurations."""
        url = f"{self.base_url}/config"
        try:
            res = requests.get(url, headers=self._get_auth_header(use_secret=False), timeout=15)
            if res.status_code == 200:
                return {'status': True, 'data': res.json()}
            return {'status': False, 'message': res.text, 'code': res.status_code}
        except Exception as e:
            logger.error(f"Myaza get_config error: {e}")
            return {'status': False, 'message': str(e)}

    def upload_media(self, file_bytes, filename, media_type='selfie'):
        """
        Uploads document or selfie media to Myaza.
        media_type: 'selfie', 'documentFront', 'documentBack', etc.
        Returns {'status': True, 'media_id': 'med_...'} or error.
        """
        url = f"{self.base_url}/upload"
        headers = self._get_auth_header(use_secret=False)
        
        # Determine explicit mimeType
        import mimetypes
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            lower = filename.lower()
            if lower.endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            elif lower.endswith('.png'):
                content_type = 'image/png'
            elif lower.endswith('.pdf'):
                content_type = 'application/pdf'
            else:
                content_type = 'image/jpeg'

        files = {
            'file': (filename, file_bytes, content_type)
        }
        data = {
            'type': media_type
        }
        try:
            res = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            if res.status_code == 200:
                json_data = res.json()
                media_id = json_data.get('mediaId')
                return {'status': True, 'media_id': media_id, 'data': json_data}
            return {'status': False, 'message': res.text, 'code': res.status_code}
        except Exception as e:
            logger.error(f"Myaza upload_media error: {e}")
            return {'status': False, 'message': str(e)}

    def submit_verification(self, country='NG', id_type='nin', id_number=None, user_data=None, media_ids=None, external_user_id=None, request_id=None):
        """
        Submits verification request to Myaza POST /verify.
        Returns immediately with 202 Accepted and verificationId.
        """
        url = f"{self.base_url}/verify"
        headers = {
            **self._get_auth_header(use_secret=False),
            'Content-Type': 'application/json'
        }

        normalized_type = self.normalize_id_type(id_type)
        req_id = request_id or str(uuid.uuid4())

        payload = {
            'country': country.upper(),
            'idType': normalized_type,
            'metadata': {
                'requestId': req_id,
            }
        }

        if id_number:
            payload['idNumber'] = str(id_number).strip()
        if user_data and isinstance(user_data, dict):
            payload['userData'] = user_data
        if media_ids and isinstance(media_ids, dict):
            payload['mediaIds'] = media_ids
        if external_user_id:
            payload['externalUserId'] = str(external_user_id)
            payload['metadata']['userId'] = str(external_user_id)

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code in [200, 202]:
                data = res.json()
                return {
                    'status': True,
                    'verification_id': data.get('verificationId'),
                    'verification_status': data.get('status', 'processing'),
                    'data': data
                }
            return {'status': False, 'message': res.text, 'code': res.status_code}
        except Exception as e:
            logger.error(f"Myaza submit_verification error: {e}")
            return {'status': False, 'message': str(e)}

    def get_status(self, verification_id):
        """
        Get minimal verification status via GET /status/:id.
        Status: 'approved', 'processing', 'pending', 'failed', 'declined', 'not_found', 'error'
        """
        if not verification_id:
            return {'status': False, 'message': 'verification_id is required'}

        url = f"{self.base_url}/status/{verification_id}"
        headers = self._get_auth_header(use_secret=False)
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return {
                    'status': True,
                    'verification_id': data.get('verificationId'),
                    'myaza_status': data.get('status'),
                    'check_status': data.get('checkStatus'),
                    'data': data
                }
            return {'status': False, 'message': res.text, 'code': res.status_code}
        except Exception as e:
            logger.error(f"Myaza get_status error: {e}")
            return {'status': False, 'message': str(e)}

    def get_full_verification(self, verification_id):
        """
        Get full verification report with PII & OCR via GET /verifications/:id using SECRET KEY.
        """
        if not verification_id:
            return {'status': False, 'message': 'verification_id is required'}

        url = f"{self.base_url}/verifications/{verification_id}"
        headers = self._get_auth_header(use_secret=True)
        try:
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return {
                    'status': True,
                    'verification_id': data.get('verificationId'),
                    'myaza_status': data.get('status'),
                    'check_status': data.get('checkStatus'),
                    'result': data.get('result'),
                    'data': data
                }
            return {'status': False, 'message': res.text, 'code': res.status_code}
        except Exception as e:
            logger.error(f"Myaza get_full_verification error: {e}")
            return {'status': False, 'message': str(e)}

    def verify_webhook_signature(self, raw_body_bytes, signature_header, secret=None):
        """
        Validates HMAC-SHA256 signature from X-Myaza-Signature header.
        signature_header: 'sha256=<hex_digest>'
        """
        if not signature_header:
            return False

        key = (secret or self.secret_key).encode('utf-8')
        expected = hmac.new(key, raw_body_bytes, hashlib.sha256).hexdigest()

        provided = signature_header
        if provided.startswith('sha256='):
            provided = provided.split('sha256=', 1)[1]

        return hmac.compare_digest(expected, provided)

    def create_session(self, workflow_id, external_user_id, user_data=None, business_data=None, metadata=None):
        """
        Creates a verification session for a workflow via POST /sessions.
        Returns {'status': True, 'session': {...}, 'url': 'https://...', 'session_id': '...'}
        """
        url = f"{self.base_url}/sessions"
        headers = {
            **self._get_auth_header(use_secret=True),
            'Content-Type': 'application/json'
        }
        payload = {
            'workflowId': str(workflow_id).strip(),
            'externalUserId': str(external_user_id),
        }
        if user_data and isinstance(user_data, dict):
            payload['userData'] = user_data
        if business_data and isinstance(business_data, dict):
            payload['business'] = business_data
        if metadata and isinstance(metadata, dict):
            payload['metadata'] = metadata

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            if res.status_code in [200, 201]:
                data = res.json()
                session = data.get('session', {})
                return {
                    'status': True,
                    'session': session,
                    'url': session.get('url'),
                    'session_id': session.get('sessionId'),
                    'data': data
                }
            return {'status': False, 'message': res.text, 'code': res.status_code}
        except Exception as e:
            logger.error(f"Myaza create_session error: {e}")
            return {'status': False, 'message': str(e)}

