import os
import logging
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv
import blockcypher
from api.models import CryptoLedger, UserSecure, CryptoLedgerSweepWallet
from api.external.encryption import Encryption

load_dotenv()

logger = logging.getLogger(__name__)

cipher = Encryption()

BITCOIN_NETWORK = os.getenv('BITCOIN_NETWORK', 'testnet')  # 'testnet' or 'mainnet'


class BitcoinWallet:
    """Class for managing Bitcoin wallet operations using BlockCypher API"""

    def __init__(self, network=BITCOIN_NETWORK):
        """
        Initialize Bitcoin wallet handler using BlockCypher

        Args:
            network: 'testnet' or 'mainnet'
        """
        self.network = network
        # BlockCypher uses 'btc' for mainnet and 'btc-testnet' for testnet
        self.coin_symbol = 'btc-testnet' if network == 'testnet' else 'btc'

    def _get_blockcypher_api_key(self):
        """Get BlockCypher API key from environment variables"""
        return os.getenv('BLOCKCYPHER_API_KEY')

    @staticmethod
    def _decrypt_key(encrypted_key):
        """Helper method to decrypt encrypted keys from database"""
        if isinstance(encrypted_key, str):
            # If stored as string representation of bytes (b'...' format)
            if encrypted_key.startswith("b'") and encrypted_key.endswith("'"):
                import ast
                encrypted_key = ast.literal_eval(encrypted_key)
            elif encrypted_key.startswith('b"') and encrypted_key.endswith('"'):
                import ast
                encrypted_key = ast.literal_eval(encrypted_key)
            else:
                encrypted_key = encrypted_key.encode('utf-8')
        return cipher.decrypt(encrypted_key)

    def generate_wallet(self, user_id, asset='BTC', chain='BTC'):
        """
        Generate a new Bitcoin wallet or return existing one

        Args:
            user_id: User ID
            asset: Asset type (default: 'BTC')
            chain: Chain type (default: 'BTC')

        Returns:
            str: Bitcoin address
        """
        try:
            # Get the UserSecure instance
            user = UserSecure.objects.get(user_id=user_id)

            # Check if wallet already exists for this user, asset, and chain
            existing_wallet = CryptoLedger.objects.filter(
                user=user,
                asset=asset,
                asset_chain=chain
            ).first()

            if existing_wallet:
                # Return existing address (decrypt it)
                address = self._decrypt_key(existing_wallet.public_key)
                return address

            # Generate new wallet using BlockCypher API
            # This creates both private key and address through BlockCypher service
            api_key = self._get_blockcypher_api_key()

            if not api_key:
                raise Exception("BlockCypher API key is required. Set BLOCKCYPHER_API_KEY environment variable.")

            keypair = blockcypher.generate_new_address(coin_symbol=self.coin_symbol, api_key=api_key)

            address = keypair['address']
            private_key = keypair['private']

            # Save to CryptoLedger model
            ledger_entry = CryptoLedger(
                user=user,
                asset=asset,
                asset_chain=chain,
                private_key=cipher.encrypt(private_key),
                public_key=cipher.encrypt(address),
                balance=0.0
            )

            ledger_entry.save()

            return address

        except UserSecure.DoesNotExist:
            raise Exception(f"User not found. Login and try again or contact support")
        except Exception as e:
            raise Exception(f"Error creating wallet: {str(e)}")

    def get_wallet_keypair(self, user_id, asset='BTC', chain='BTC'):
        """
        Get the private key for a user's wallet

        Args:
            user_id: User ID
            asset: Asset type
            chain: Chain type

        Returns:
            str: Private key (as stored by BlockCypher)
        """
        try:
            user = UserSecure.objects.get(user_id=user_id)
            wallet_entry = CryptoLedger.objects.filter(
                user=user,
                asset=asset,
                asset_chain=chain
            ).first()

            if not wallet_entry:
                raise Exception(f"Wallet not found for user {user_id}")

            private_key = self._decrypt_key(wallet_entry.private_key)
            return private_key

        except UserSecure.DoesNotExist:
            raise Exception(f"User not found")
        except Exception as e:
            raise Exception(f"Error getting wallet keypair: {str(e)}")

    def get_balance(self, address, asset_code='BTC'):
        """
        Get balance for a Bitcoin address

        Args:
            address: Bitcoin address
            asset_code: Asset code (default: 'BTC')

        Returns:
            Decimal: Balance amount in BTC
        """
        try:
            # Get address details from BlockCypher
            address_details = blockcypher.get_address_details(address, coin_symbol=self.coin_symbol)

            # Get balance in satoshis and convert to BTC
            balance_satoshis = address_details.get('balance', 0)
            balance_btc = Decimal(str(balance_satoshis)) / Decimal('100000000')  # 1 BTC = 100,000,000 satoshis
            return balance_btc
        except Exception as e:
            raise Exception(f"Error getting balance: {str(e)}")

    def get_balance_usd(self, address, asset_code='BTC'):
        """
        Get balance in USD equivalent

        Args:
            address: Bitcoin address
            asset_code: Asset code (default: 'BTC')

        Returns:
            dict: {
                'balance': Decimal,  # Original balance
                'balance_usd': Decimal,  # USD equivalent
                'asset': str,  # Asset code
                'usd_rate': Decimal  # Exchange rate
            }
        """
        try:
            balance = self.get_balance(address, asset_code)
            usd_rate = self._get_btc_usd_rate()
            balance_usd = balance * usd_rate

            return {
                'balance': balance,
                'balance_usd': balance_usd,
                'asset': asset_code,
                'usd_rate': usd_rate
            }
        except Exception as e:
            raise Exception(f"Error getting USD balance: {str(e)}")

    def _get_btc_usd_rate(self):
        """
        Get BTC to USD exchange rate

        Returns:
            Decimal: Exchange rate
        """
        try:
            import requests

            # Get BTC price from CoinGecko
            response = requests.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return Decimal(str(data.get('bitcoin', {}).get('usd', 50000)))  # Default fallback
            else:
                return Decimal('50000')  # Default fallback rate

        except Exception as e:
            return Decimal('50000')  # Default fallback rate

    def sweep_funds(self, user_id, asset='BTC', chain='BTC', destination_wallet=None):
        try:
            # Get private key and address
            private_key = self.get_wallet_keypair(user_id, asset, chain)

            # Get user wallet entry to get the address
            user = UserSecure.objects.get(user_id=user_id)
            wallet_entry = CryptoLedger.objects.filter(
                user=user,
                asset=asset,
                asset_chain=chain
            ).first()

            if not wallet_entry:
                raise Exception(f"Wallet not found for user {user_id}")

            from_address = self._decrypt_key(wallet_entry.public_key)

            # Get destination wallet from model (not hardcoded)
            if not destination_wallet:
                try:
                    sweep_wallet = CryptoLedgerSweepWallet.objects.get(
                        asset=asset,
                        asset_chain=chain,
                        is_active=True
                    )
                    destination_wallet = sweep_wallet.public_key
                except CryptoLedgerSweepWallet.DoesNotExist:
                    raise Exception(f"No active sweep wallet configured for {asset} on {chain}. Please configure a sweep wallet in admin settings.")

            # Get current balance
            balance = self.get_balance(from_address, asset)

            if balance <= 0:
                return {
                    'status': False,
                    'message': 'No funds to sweep',
                    'amount_swept': Decimal('0'),
                    'from_wallet': from_address,
                    'to_wallet': destination_wallet
                }

            # Convert balance to satoshis for transaction
            amount_satoshis = int(float(balance) * 100000000)

            # Send transaction using BlockCypher API
            blockcypher_api_key = self._get_blockcypher_api_key()
            if not blockcypher_api_key:
                raise Exception("BlockCypher API key is required for transactions. Set BLOCKCYPHER_API_KEY environment variable.")

            tx = blockcypher.simple_spend(
                from_privkey=private_key,
                to_address=destination_wallet,
                to_satoshis=amount_satoshis,
                coin_symbol=self.coin_symbol,
                api_key=blockcypher_api_key
            )
            tx_hash = tx.get('tx', {}).get('hash', '')

            # Estimate fee (BlockCypher handles this internally)
            estimated_fee = Decimal('0.00001')  # Rough estimate for BTC fee

            return {
                'status': True,
                'transaction_id': tx_hash,
                'amount_swept': balance,
                'fee_paid': estimated_fee,
                'from_wallet': from_address,
                'to_wallet': destination_wallet
            }

        except UserSecure.DoesNotExist:
            raise Exception(f"User not found")
        except Exception as e:
            raise Exception(f"Error sweeping funds: {str(e)}")


def get_btc_to_ngn_rate():
    """
    Get BTC to NGN exchange rate
    First get BTC to USD, then USD to NGN
    """
    try:
        import requests

        # Get BTC to USD rate from CoinGecko
        btc_response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
            timeout=10
        )
        if btc_response.status_code == 200:
            btc_data = btc_response.json()
            btc_to_usd = Decimal(str(btc_data.get('bitcoin', {}).get('usd', 50000)))
        else:
            btc_to_usd = Decimal('50000')  # Default fallback

        # Get USD to NGN rate
        usd_response = requests.get(
            'https://api.exchangerate-api.com/v4/latest/USD',
            timeout=10
        )
        if usd_response.status_code == 200:
            usd_data = usd_response.json()
            usd_to_ngn = Decimal(str(usd_data.get('rates', {}).get('NGN', 1500)))
        else:
            usd_to_ngn = Decimal('1500')  # Default fallback

        # Calculate BTC to NGN
        btc_to_ngn = btc_to_usd * usd_to_ngn
        return btc_to_ngn

    except Exception as e:
        return Decimal('75000000')  # Default fallback rate (50,000 USD * 1,500 NGN)


def get_crypto_sweep_fee_btc():
    """
    Get the crypto sweep fee in BTC from admin settings.

    IMPORTANT: This function ALWAYS uses the admin-configured value from the database.
    The hardcoded 0.0001 BTC is ONLY used as a fallback if:
    - Admin settings are not configured
    - Admin settings don't contain crypto_sweep_fee_btc
    - An error occurs reading the settings

    Returns the configured fee (can be 0 if admin sets it to 0) or defaults to 0.0001 BTC if not set.
    """
    try:
        # Get any admin user's settings (they should all have the same global settings)
        admin = UserSecure.objects.filter(is_superuser=True).first()
        if admin and admin.admin_settings:
            fee = admin.admin_settings.get('crypto_sweep_fee_btc')
            if fee is not None:
                try:
                    fee_decimal = Decimal(str(fee))
                    if fee_decimal >= 0:  # Allow 0 fee if admin sets it
                        return fee_decimal
                    else:
                        pass
                except (ValueError, TypeError) as e:
                    pass

        # Default to 0.0001 BTC ONLY if admin setting is not configured
        # This fallback should rarely be used in production
        return Decimal('0.0001')
    except Exception as e:
        # Fallback only used if there's an error reading settings
        return Decimal('0.0001')
