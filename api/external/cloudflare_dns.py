"""
Cloudflare DNS API Service.

Manages DNS records on Cloudflare for store subdomain routing.
When a merchant sets their store_domain (e.g. shop.maxyfleets.com),
this service creates/updates/removes the corresponding DNS A record
so the subdomain resolves to the application server.

Security:
- API token is read from environment variables, never hardcoded
- Token is never logged or exposed in error messages
- All inputs are validated before making API calls
- Cloudflare error details are logged server-side only
"""

import os
import re
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Cloudflare API v4 base URL
CLOUDFLARE_API_BASE = 'https://api.cloudflare.com/client/v4'


class CloudflareDNSError(Exception):
    """Custom exception for Cloudflare DNS operations."""
    pass


class CloudflareDNS:
    """
    Service class for interacting with the Cloudflare DNS API.

    Usage:
        cf = CloudflareDNS()
        cf.upsert_subdomain_record('shop', '1.2.3.4')
        cf.remove_subdomain_record('shop')
    """

    def __init__(self):
        self.api_token = getattr(settings, 'CLOUDFLARE_API_TOKEN', '') or os.getenv('CLOUDFLARE_API_TOKEN', '')
        self.account_id = getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', '') or os.getenv('CLOUDFLARE_ACCOUNT_ID', '')
        self.target_domain = getattr(settings, 'CLOUDFLARE_TARGET_DOMAIN', '') or os.getenv('CLOUDFLARE_TARGET_DOMAIN', '')
        self._zone_id = None  # Cached after first lookup

        if not self.api_token:
            raise CloudflareDNSError('CLOUDFLARE_API_TOKEN is not configured.')
        if not self.target_domain:
            raise CloudflareDNSError('CLOUDFLARE_TARGET_DOMAIN is not configured.')

    @property
    def _headers(self):
        """Authorization headers for Cloudflare API requests."""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

    # ─── Zone Management ───────────────────────────────────────────

    def get_zone_id(self, domain=None):
        """
        Look up the Cloudflare Zone ID for the target domain.
        Result is cached after the first successful call.

        Args:
            domain: Domain name to look up. Defaults to CLOUDFLARE_TARGET_DOMAIN.

        Returns:
            str: The Zone ID.

        Raises:
            CloudflareDNSError: If the zone cannot be found.
        """
        if self._zone_id:
            return self._zone_id

        domain = domain or self.target_domain

        try:
            response = requests.get(
                f'{CLOUDFLARE_API_BASE}/zones',
                headers=self._headers,
                params={'name': domain, 'status': 'active'},
                timeout=15,
            )
            if not response.ok:
                logger.error(f'Cloudflare HTTP Error: {response.status_code} - {response.text}')
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                errors = data.get('errors', [])
                logger.error('Cloudflare zone lookup failed: %s', errors)
                raise CloudflareDNSError('Failed to look up DNS zone.')

            zones = data.get('result', [])
            if not zones:
                raise CloudflareDNSError(f'No active zone found for domain: {domain}')

            self._zone_id = zones[0]['id']
            return self._zone_id

        except requests.RequestException as e:
            logger.error('Cloudflare API request failed during zone lookup: %s', str(e))
            raise CloudflareDNSError('Failed to connect to Cloudflare API.') from e

    # ─── DNS Record CRUD ──────────────────────────────────────────

    def list_dns_records(self, zone_id, name=None, record_type=None):
        """
        List DNS records in a zone, optionally filtered by name and type.

        Args:
            zone_id: Cloudflare zone ID.
            name: Full record name to filter by (e.g. 'shop.maxyfleets.com').
            record_type: DNS record type to filter (e.g. 'A', 'CNAME').

        Returns:
            list: List of DNS record dicts from Cloudflare.
        """
        params = {}
        if name:
            params['name'] = name
        if record_type:
            params['type'] = record_type

        try:
            response = requests.get(
                f'{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records',
                headers=self._headers,
                params=params,
                timeout=15,
            )
            if not response.ok:
                logger.error(f'Cloudflare HTTP Error: {response.status_code} - {response.text}')
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                logger.error('Cloudflare list records failed: %s', data.get('errors', []))
                return []

            return data.get('result', [])

        except requests.RequestException as e:
            logger.error('Cloudflare API request failed listing DNS records: %s', str(e))
            return []

    def create_dns_record(self, zone_id, record_type, name, content, proxied=True, ttl=1):
        """
        Create a new DNS record in the specified zone.

        Args:
            zone_id: Cloudflare zone ID.
            record_type: DNS record type ('A', 'CNAME', etc.).
            name: Record name (e.g. 'shop' for shop.maxyfleets.com).
            content: Record value (IP address for A, hostname for CNAME).
            proxied: Whether to proxy through Cloudflare (default True).
            ttl: Time to live. 1 = automatic when proxied.

        Returns:
            dict: The created DNS record from Cloudflare.

        Raises:
            CloudflareDNSError: If creation fails.
        """
        payload = {
            'type': record_type,
            'name': name,
            'content': content,
            'proxied': proxied,
            'ttl': ttl,
        }

        try:
            response = requests.post(
                f'{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records',
                headers=self._headers,
                json=payload,
                timeout=15,
            )
            if not response.ok:
                logger.error(f'Cloudflare HTTP Error: {response.status_code} - {response.text}')
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                errors = data.get('errors', [])
                logger.error('Cloudflare create record failed: %s', errors)
                raise CloudflareDNSError('Failed to create DNS record.')

            record = data.get('result', {})
            logger.info('Cloudflare DNS record created: %s -> %s (ID: %s)', name, content, record.get('id'))
            return record

        except requests.RequestException as e:
            logger.error('Cloudflare API request failed creating DNS record: %s', str(e))
            raise CloudflareDNSError('Failed to create DNS record.') from e

    def update_dns_record(self, zone_id, record_id, record_type, name, content, proxied=True):
        """
        Update an existing DNS record.

        Args:
            zone_id: Cloudflare zone ID.
            record_id: Cloudflare DNS record ID to update.
            record_type: DNS record type.
            name: Record name.
            content: New record value.
            proxied: Whether to proxy through Cloudflare.

        Returns:
            dict: The updated DNS record from Cloudflare.

        Raises:
            CloudflareDNSError: If update fails.
        """
        payload = {
            'type': record_type,
            'name': name,
            'content': content,
            'proxied': proxied,
        }

        try:
            response = requests.put(
                f'{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records/{record_id}',
                headers=self._headers,
                json=payload,
                timeout=15,
            )
            if not response.ok:
                logger.error(f'Cloudflare HTTP Error: {response.status_code} - {response.text}')
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                errors = data.get('errors', [])
                logger.error('Cloudflare update record failed: %s', errors)
                raise CloudflareDNSError('Failed to update DNS record.')

            record = data.get('result', {})
            logger.info('Cloudflare DNS record updated: %s -> %s (ID: %s)', name, content, record.get('id'))
            return record

        except requests.RequestException as e:
            logger.error('Cloudflare API request failed updating DNS record: %s', str(e))
            raise CloudflareDNSError('Failed to update DNS record.') from e

    def delete_dns_record(self, zone_id, record_id):
        """
        Delete a DNS record.

        Args:
            zone_id: Cloudflare zone ID.
            record_id: Cloudflare DNS record ID to delete.

        Returns:
            bool: True if deletion was successful.

        Raises:
            CloudflareDNSError: If deletion fails.
        """
        try:
            response = requests.delete(
                f'{CLOUDFLARE_API_BASE}/zones/{zone_id}/dns_records/{record_id}',
                headers=self._headers,
                timeout=15,
            )
            if not response.ok:
                logger.error(f'Cloudflare HTTP Error: {response.status_code} - {response.text}')
            response.raise_for_status()
            data = response.json()

            if not data.get('success'):
                errors = data.get('errors', [])
                logger.error('Cloudflare delete record failed: %s', errors)
                raise CloudflareDNSError('Failed to delete DNS record.')

            logger.info('Cloudflare DNS record deleted: %s', record_id)
            return True

        except requests.RequestException as e:
            logger.error('Cloudflare API request failed deleting DNS record: %s', str(e))
            raise CloudflareDNSError('Failed to delete DNS record.') from e

    # ─── High-Level Operations ────────────────────────────────────

    def upsert_subdomain_record(self, subdomain, target_ip=None):
        """
        Create or update a DNS A record for a subdomain under the target domain.

        This is the primary method for setting up store subdomains.
        It handles the full flow: get zone → check existing → create/update.

        Args:
            subdomain: The subdomain part only (e.g. 'shop', not 'shop.maxyfleets.com').
            target_ip: Server IP to point the record to. Defaults to SERVER_IP env var.

        Returns:
            dict: {
                'record_id': str,
                'zone_id': str,
                'full_domain': str,
                'record_type': str,
                'target_value': str,
            }

        Raises:
            CloudflareDNSError: If any step fails.
        """
        # Validate subdomain
        subdomain = self._validate_subdomain(subdomain)

        # Determine target
        if not target_ip:
            target_ip = os.getenv('SERVER_TARGET', os.getenv('SERVER_IP', '127.0.0.1'))
            
        import re
        is_ip = bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target_ip))
        record_type = 'A' if is_ip else 'CNAME'

        full_domain = f'{subdomain}.{self.target_domain}'
        zone_id = self.get_zone_id()

        # Check if a record already exists for this subdomain (same type)
        existing_records = self.list_dns_records(zone_id, name=full_domain, record_type=record_type)

        if existing_records:
            # Update existing record
            record = existing_records[0]
            updated = self.update_dns_record(
                zone_id=zone_id,
                record_id=record['id'],
                record_type=record_type,
                name=subdomain,
                content=target_ip,
                proxied=True,
            )
            return {
                'record_id': updated['id'],
                'zone_id': zone_id,
                'full_domain': full_domain,
                'record_type': record_type,
                'target_value': target_ip,
            }
        else:
            # Also check for conflicts of the OTHER type before creating
            other_type = 'CNAME' if is_ip else 'A'
            conflict_records = self.list_dns_records(zone_id, name=full_domain, record_type=other_type)
            if conflict_records:
                # Remove conflicting record first
                for conf in conflict_records:
                    self.delete_dns_record(zone_id, conf['id'])
                    logger.info('Removed conflicting %s record for %s', other_type, full_domain)

            # Localhost workaround: Cloudflare cannot proxy 127.0.0.1
            proxied = True
            if target_ip == '127.0.0.1' or target_ip.startswith('192.168.') or target_ip.startswith('10.'):
                proxied = False
                logger.warning('Disabling proxy for local IP address %s to prevent Cloudflare 400 error.', target_ip)

            # Create new record
            created = self.create_dns_record(
                zone_id=zone_id,
                record_type=record_type,
                name=subdomain,
                content=target_ip,
                proxied=proxied,
            )
            return {
                'record_id': created['id'],
                'zone_id': zone_id,
                'full_domain': full_domain,
                'record_type': record_type,
                'target_value': target_ip,
            }

    def remove_subdomain_record(self, subdomain):
        """
        Remove a DNS record for a subdomain under the target domain.

        Used when a store domain is cleared or changed.

        Args:
            subdomain: The subdomain part only (e.g. 'shop').

        Returns:
            bool: True if the record was found and deleted, False if no record existed.
        """
        subdomain = self._validate_subdomain(subdomain)
        full_domain = f'{subdomain}.{self.target_domain}'
        zone_id = self.get_zone_id()

        # Look for both A and CNAME records
        deleted_any = False
        for record_type in ('A', 'CNAME'):
            records = self.list_dns_records(zone_id, name=full_domain, record_type=record_type)
            for record in records:
                self.delete_dns_record(zone_id, record['id'])
                deleted_any = True

        return deleted_any

    # ─── Validation Helpers ───────────────────────────────────────

    @staticmethod
    def _validate_subdomain(subdomain):
        """
        Validate and sanitize a subdomain string.

        Args:
            subdomain: Raw subdomain input.

        Returns:
            str: Sanitized subdomain.

        Raises:
            CloudflareDNSError: If the subdomain is invalid.
        """
        if not subdomain:
            raise CloudflareDNSError('Subdomain cannot be empty.')

        subdomain = subdomain.strip().lower()

        # Remove the target domain suffix if the full domain was passed
        target_domain = getattr(settings, 'CLOUDFLARE_TARGET_DOMAIN', '') or os.getenv('CLOUDFLARE_TARGET_DOMAIN', '')
        if target_domain and subdomain.endswith(f'.{target_domain}'):
            subdomain = subdomain[: -(len(target_domain) + 1)]

        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', subdomain):
            raise CloudflareDNSError(
                'Invalid subdomain. Only lowercase letters, numbers, and hyphens are allowed. '
                'Cannot start or end with a hyphen.'
            )

        if len(subdomain) > 63:
            raise CloudflareDNSError('Subdomain cannot exceed 63 characters.')

        # Prevent reserved subdomains
        reserved = getattr(settings, 'RESERVED_SUBDOMAINS', set())
        if subdomain in reserved:
            raise CloudflareDNSError(f'The subdomain "{subdomain}" is reserved and cannot be used.')

        return subdomain

    @staticmethod
    def extract_subdomain(full_domain):
        """
        Extract the subdomain part from a full domain string.

        Args:
            full_domain: Full domain (e.g. 'shop.maxyfleets.com').

        Returns:
            str or None: The subdomain part, or None if not a valid subdomain of the target domain.
        """
        if not full_domain:
            return None

        full_domain = full_domain.strip().lower()
        target_domain = getattr(settings, 'CLOUDFLARE_TARGET_DOMAIN', '') or os.getenv('CLOUDFLARE_TARGET_DOMAIN', '')

        if not target_domain:
            return None

        if full_domain.endswith(f'.{target_domain}'):
            subdomain = full_domain[: -(len(target_domain) + 1)]
            if subdomain and '.' not in subdomain:
                return subdomain

        return None
