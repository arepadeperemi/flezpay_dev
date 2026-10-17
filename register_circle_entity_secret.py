#!/usr/bin/env python3
"""
Circle USDC Entity Secret Registration

This script registers an entity secret with Circle's API for USDC wallet operations.
The entity secret must be generated first using generate_circle_entity_secret.py

Usage:
    python register_circle_entity_secret.py

Environment Variables Required:
    - CIRCLE_USDC_API_KEY or CIRCLE_USDC_TESTNET: Your Circle API key
    - HEX_ENCODED_ENTITY_SECRET_KEY: The entity secret to register (32 bytes as hex)
    - CIRCLE_BASE_URL: Circle API base URL (optional, defaults to https://api.circle.com/v1)
"""

import requests
import json
import uuid
import os
import base64
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Always import crypto libraries for ciphertext generation
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

def uuid7str():
    """Generate UUID7 string - using uuid4 as fallback if uuid7 not available"""
    if hasattr(uuid, 'uuid7'):
        return str(uuid.uuid7())
    try:
        from uuid_extensions import uuid7str as _uuid7str
        return _uuid7str()
    except ImportError:
        return str(uuid.uuid4())

def get_circle_public_key(api_key, base_url="https://api.circle.com/v1"):
    """
    Get Circle's public key for encryption
    """
    headers = {
        "X-Request-Id": uuid7str(),
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Use the base_url directly if it ends with /v1, otherwise append /v1
    if base_url.endswith('/v1'):
        url = f"{base_url}/w3s/config/entity/publicKey"
    else:
        url = f"{base_url}/v1/w3s/config/entity/publicKey"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if 'data' in data and 'publicKey' in data['data']:
            return data['data']['publicKey']
        else:
            raise Exception("Public key not found in response")

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to get Circle public key: {e}")

def generate_entity_secret_ciphertext(api_key, entity_secret_hex, base_url="https://api.circle.com/v1"):
    """
    Generate encrypted entity secret ciphertext for Circle API registration
    """
    # Validate entity secret format
    hex_clean = ''.join(c for c in entity_secret_hex if c in '0123456789abcdefABCDEF')

    if len(hex_clean) != 64:
        raise Exception(f"Invalid entity secret length. Expected 64 hex characters, got {len(hex_clean)}. Original length: {len(entity_secret_hex)}")

    entity_secret = bytes.fromhex(hex_clean)

    if len(entity_secret) != 32:
        raise Exception(f"Invalid entity secret byte length. Expected 32 bytes, got {len(entity_secret)}")

    # Get Circle's public key
    public_key_pem = get_circle_public_key(api_key, base_url)

    # Import the public key
    public_key = RSA.importKey(public_key_pem)

    # Encrypt the entity secret
    cipher_rsa = PKCS1_OAEP.new(key=public_key, hashAlgo=SHA256)
    encrypted_data = cipher_rsa.encrypt(entity_secret)

    # Encode to base64
    ciphertext = base64.b64encode(encrypted_data)

    return ciphertext.decode()

def register_entity_secret(api_key, entity_secret_ciphertext, base_url="https://api.circle.com/v1"):
    """
    Register the entity secret ciphertext with Circle API
    """
    headers = {
        "X-Request-Id": uuid7str(),
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Use the base_url directly if it ends with /v1, otherwise append /v1
    if base_url.endswith('/v1'):
        url = f"{base_url}/w3s/config/entity/entitySecret"
    else:
        url = f"{base_url}/v1/w3s/config/entity/entitySecret"

    data = {
        "entitySecretCiphertext": entity_secret_ciphertext
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to register entity secret: {e}"
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                error_msg += f"\nResponse: {json.dumps(error_data, indent=2)}"
            except:
                error_msg += f"\nResponse: {e.response.text}"
        raise Exception(error_msg)

def save_recovery_file(recovery_data, filename=None):
    """
    Save the recovery file to disk
    """
    if filename is None:
        timestamp = int(datetime.now().timestamp() * 1000)
        filename = f"recovery_file_{timestamp}.dat"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(recovery_data)
        print(f"✓ Recovery file saved successfully at: {filename}")
        return filename
    except Exception as e:
        print(f"✗ Error saving recovery file: {e}")
        print("Please save the recovery data manually:")
        print(recovery_data)
        return None

def main():
    print("Circle USDC Entity Secret Registration")
    print("=" * 45)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Get required environment variables
    api_key = os.getenv('CIRCLE_USDC_TESTNET') or os.getenv('CIRCLE_USDC_API_KEY')
    entity_secret = os.getenv('HEX_ENCODED_ENTITY_SECRET_KEY')
    base_url = os.getenv('CIRCLE_BASE_URL', 'https://api.circle.com/v1')

    if not api_key:
        print("✗ Error: Circle API key not found.")
        print("Please set CIRCLE_USDC_TESTNET or CIRCLE_USDC_API_KEY environment variable.")
        sys.exit(1)

    if not entity_secret:
        print("✗ Error: Entity secret not found.")
        print("Please set HEX_ENCODED_ENTITY_SECRET_KEY environment variable.")
        print("Run 'python generate_circle_entity_secret.py' to generate one first.")
        sys.exit(1)

    print("Configuration:")
    print(f"  API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else api_key}")
    print(f"  Entity Secret: {entity_secret[:8]}...{entity_secret[-8:] if len(entity_secret) > 16 else entity_secret}")
    print(f"  Base URL: {base_url}")
    print()

    try:
        # Step 1: Generate ciphertext
        print("Step 1: Generating entity secret ciphertext...")
        ciphertext = generate_entity_secret_ciphertext(api_key, entity_secret, base_url)
        print("✓ Ciphertext generated successfully")
        print()

        # Step 2: Register with Circle
        print("Step 2: Registering entity secret with Circle...")
        registration_result = register_entity_secret(api_key, ciphertext, base_url)
        print("✓ Entity secret registered successfully!")
        print()

        # Step 3: Save recovery file
        print("Step 3: Saving recovery file...")
        if 'data' in registration_result and 'recoveryFile' in registration_result['data']:
            recovery_file = registration_result['data']['recoveryFile']
            saved_path = save_recovery_file(recovery_file)
            print()

            if saved_path:
                print("🎉 Registration completed successfully!")
                print("Recovery file saved for backup purposes.")
                print("Keep this file secure as it contains your wallet recovery information.")
            else:
                print("⚠️ Registration completed but recovery file could not be saved automatically.")
                print("Please save the recovery data manually from above.")
        else:
            print("⚠️ Registration completed but no recovery file found in response.")
            print("Response:", json.dumps(registration_result, indent=2))

    except Exception as e:
        print(f"✗ Error during registration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
