# Circle USDC Entity Setup Guide

This guide explains how to set up a new entity secret for Circle USDC wallet operations.

## Overview

Circle USDC requires an entity secret to be registered before you can create and manage developer-controlled wallets. This is a one-time setup process that needs to be done for each Circle account.

## Prerequisites

- Circle API key (testnet or mainnet)
- Python environment with required dependencies
- `.env` file for storing configuration

## Step 1: Generate Entity Secret

Run the entity secret generator:

```bash
python generate_circle_entity_secret.py
```

This will:
- Generate a new 32-byte random entity secret
- Display the secret in a secure format
- Show instructions for adding it to your `.env` file
- Optionally update your `.env` file automatically (if run interactively)

**Important:** Save the generated entity secret securely! You cannot recover it if lost.

## Step 2: Configure Environment Variables

Add the following to your `.env` file:

```env
# Circle API Configuration
CIRCLE_USDC_API_KEY=your_circle_api_key_here
# or for testnet:
CIRCLE_USDC_TESTNET=your_testnet_api_key_here

# Entity Secret (generated in Step 1)
HEX_ENCODED_ENTITY_SECRET_KEY=your_generated_entity_secret_here

# Optional: Custom base URL
CIRCLE_BASE_URL=https://api.circle.com/v1
```

## Step 3: Register Entity Secret

Run the registration script:

```bash
python register_circle_entity_secret.py
```

This will:
- Load your API key and entity secret from environment variables
- Encrypt the entity secret using Circle's public key
- Register the encrypted secret with Circle's API
- Save a recovery file for backup purposes

## Step 4: Verify Setup

Test that your Circle USDC integration works:

```bash
python manage.py shell -c "
from api.crypto.circle_usdc import CircleUSDC
circle = CircleUSDC()
print('✓ Circle USDC client initialized successfully')
"
```

## Files Created

- `generate_circle_entity_secret.py` - Generates new entity secrets
- `register_circle_entity_secret.py` - Registers entity secrets with Circle
- Recovery file (timestamped `.dat` file) - Contains wallet recovery information

## Security Notes

- **Never commit entity secrets to version control**
- **Store recovery files securely** - they contain your wallet recovery information
- **Keep backups** of both the entity secret and recovery file
- **Use different entity secrets** for testnet and mainnet environments

## Troubleshooting

### "Circle API key not configured"
- Ensure `CIRCLE_USDC_API_KEY` or `CIRCLE_USDC_TESTNET` is set in your `.env` file

### "Entity secret not configured"
- Ensure `HEX_ENCODED_ENTITY_SECRET_KEY` is set in your `.env` file
- Run the generator script first if you don't have an entity secret

### "409 Conflict" during registration
- The entity secret is already registered with Circle
- This is normal if you're re-running the registration script

### "404 Not Found" errors
- Check that your API key is valid and has the correct permissions
- Verify you're using the correct base URL for your environment (testnet vs mainnet)

## API Reference

- [Circle Developer Documentation](https://developers.circle.com/)
- [Entity Secret Registration](https://developers.circle.com/wallets/dev-controlled/register-entity-secret)
