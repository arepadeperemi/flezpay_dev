#!/usr/bin/env python3
"""
Circle USDC Entity Secret Generator

This script generates a new entity secret for Circle USDC wallet operations.
The entity secret is a 32-byte random value that needs to be registered with Circle.

Usage:
    python generate_circle_entity_secret.py

Environment Variables Required:
    - CIRCLE_USDC_API_KEY or CIRCLE_USDC_TESTNET: Your Circle API key
    - CIRCLE_BASE_URL: Circle API base URL (optional, defaults to https://api.circle.com/v1)
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_entity_secret():
    """
    Generate a new 32-byte entity secret and return it as hex string
    """
    # Generate a random 32-byte secret and convert it to a hex string
    entity_secret = os.urandom(32).hex()
    return entity_secret

def print_entity_secret_info(entity_secret):
    """
    Print formatted information about the generated entity secret
    """
    message = 'Register the following entity secret using the registerEntitySecretCiphertext method or through the Developer Console and save the secret somewhere safe.\n'

    entity_secret_message = f'!!!! ENTITY SECRET: {entity_secret} !!!!'
    top_bottom_border = '=' * len(entity_secret_message)

    print(message)
    print(top_bottom_border)
    print(entity_secret_message)
    print(f'{top_bottom_border}\n')

    print('IMPORTANT: Save this entity secret securely! You will need it to register with Circle.')
    print('The entity secret should be set as HEX_ENCODED_ENTITY_SECRET_KEY in your environment variables.')
    print()

def main():
    print("Circle USDC Entity Secret Generator")
    print("=" * 40)
    print(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Generate the entity secret
    entity_secret = generate_entity_secret()

    # Print formatted information
    print_entity_secret_info(entity_secret)

    # Print environment variable setup instructions
    print("Environment Variable Setup:")
    print("Add the following to your .env file:")
    print(f"HEX_ENCODED_ENTITY_SECRET_KEY={entity_secret}")
    print()

    print("Next Steps:")
    print("1. Save this entity secret securely")
    print("2. Add it to your environment variables")
    print("3. Run the registration script: python register_circle_entity_secret.py")
    print()

    # Ask user if they want to save to .env file (skip in non-interactive mode)
    try:
        save_to_env = input("Do you want to automatically add this to your .env file? (y/n): ").strip().lower()
        should_save = save_to_env == 'y'
    except EOFError:
        print("Running in non-interactive mode. Skipping automatic .env file update.")
        print("Please manually add the HEX_ENCODED_ENTITY_SECRET_KEY to your .env file.")
        return entity_secret

    if should_save:
        env_file_path = '.env'
        try:
            # Read existing .env file
            env_lines = []
            if os.path.exists(env_file_path):
                with open(env_file_path, 'r') as f:
                    env_lines = f.readlines()

            # Check if HEX_ENCODED_ENTITY_SECRET_KEY already exists
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith('HEX_ENCODED_ENTITY_SECRET_KEY='):
                    env_lines[i] = f'HEX_ENCODED_ENTITY_SECRET_KEY={entity_secret}\n'
                    found = True
                    break

            # Add new line if not found
            if not found:
                env_lines.append(f'\nHEX_ENCODED_ENTITY_SECRET_KEY={entity_secret}\n')

            # Write back to .env file
            with open(env_file_path, 'w') as f:
                f.writelines(env_lines)

            print(f"✓ Entity secret saved to {env_file_path}")

        except Exception as e:
            print(f"✗ Error saving to .env file: {e}")
            print("Please manually add the environment variable to your .env file.")

    return entity_secret

if __name__ == "__main__":
    entity_secret = main()
    print(f"\nGenerated Entity Secret: {entity_secret}")
    sys.exit(0)
