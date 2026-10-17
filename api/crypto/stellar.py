import requests
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from stellar_sdk.exceptions import NotFoundError, BadRequestError
from django.conf import settings
from decimal import Decimal
from datetime import datetime
from api.models import CryptoLedger, UserSecure, CryptoLedgerSweepWallet
from api.external.encryption import Encryption
import os

cipher = Encryption()

STELLAR_NETWORK = os.getenv('STELLAR_NETWORK', 'testnet')  # 'testnet' or 'public'
STELLAR_HORIZON_URL = os.getenv('STELLAR_HORIZON_URL', 'https://horizon-testnet.stellar.org')


class StellarWallet:
    """Class for managing Stellar wallet operations"""
    
    def __init__(self, network=STELLAR_NETWORK, horizon_url=STELLAR_HORIZON_URL):
        """
        Initialize Stellar wallet handler
        
        Args:
            network: 'testnet' or 'public'
            horizon_url: Stellar Horizon server URL
        """
        self.network = network
        self.horizon_url = horizon_url
        self.server = Server(horizon_url)
        self.network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE if network == 'testnet' else Network.PUBLIC_NETWORK_PASSPHRASE
    
    @staticmethod
    def _decrypt_key(encrypted_key):
        """Helper method to decrypt encrypted keys from database"""
        if not encrypted_key:
            return ""
        if isinstance(encrypted_key, str):
            # If already a valid plain Stellar public key address
            if len(encrypted_key) == 56 and encrypted_key.startswith('G'):
                return encrypted_key
            # If stored as string representation of bytes (b'...' format)
            if encrypted_key.startswith("b'") and encrypted_key.endswith("'"):
                import ast
                try:
                    encrypted_key = ast.literal_eval(encrypted_key)
                except Exception:
                    pass
            elif encrypted_key.startswith('b"') and encrypted_key.endswith('"'):
                import ast
                try:
                    encrypted_key = ast.literal_eval(encrypted_key)
                except Exception:
                    pass
            else:
                try:
                    encrypted_key = encrypted_key.encode('utf-8')
                except Exception:
                    pass
        try:
            decrypted = cipher.decrypt(encrypted_key)
            if isinstance(decrypted, bytes):
                decrypted = decrypted.decode('utf-8')
            return decrypted
        except Exception:
            if isinstance(encrypted_key, bytes):
                return encrypted_key.decode('utf-8', errors='ignore')
            return str(encrypted_key)

    def generate_wallet(self, user_id, asset='XLM', chain='XLM'):
        """
        Generate a new Stellar wallet or return existing one
        
        Args:
            user_id: User ID
            asset: Asset type (default: 'XLM')
            chain: Chain type (default: 'XLM')
            
        Returns:
            str: Public key (wallet address)
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
                # Return existing public key (decrypt it)
                public_key = self._decrypt_key(existing_wallet.public_key)
                return public_key

            # Generate new keypair
            keypair = Keypair.random()
            public_key = keypair.public_key
            private_key = keypair.secret

            # Save to CryptoLedger model
            ledger_entry = CryptoLedger(
                user=user,
                asset=asset,
                asset_chain=chain,
                private_key=cipher.encrypt(private_key),
                public_key=cipher.encrypt(public_key),
                balance=0.0
            )

            ledger_entry.save()

            return public_key

        except UserSecure.DoesNotExist:
            raise Exception(f"User not found. Login and try again or contact support")
        except Exception as e:
            raise Exception(f"Error creating wallet: {str(e)}")
    
    def get_wallet_keypair(self, user_id, asset='XLM', chain='XLM'):
        """
        Get the keypair for a user's wallet
        
        Args:
            user_id: User ID
            asset: Asset type
            chain: Chain type
            
        Returns:
            Keypair: Stellar keypair object
        """
        try:
            user = UserSecure.objects.get(user_id=user_id)
            wallet = CryptoLedger.objects.filter(
                user=user,
                asset=asset,
                asset_chain=chain
            ).first()
            
            if not wallet:
                raise Exception(f"Wallet not found for user {user_id}")
            
            private_key = self._decrypt_key(wallet.private_key)
            return Keypair.from_secret(private_key)
            
        except UserSecure.DoesNotExist:
            raise Exception(f"User not found")
        except Exception as e:
            raise Exception(f"Error getting wallet keypair: {str(e)}")
    
    def get_balance(self, public_key, asset_code='XLM'):
        """
        Get balance for a specific asset in a wallet
        
        Args:
            public_key: Wallet public key
            asset_code: Asset code (default: 'XLM' for native)
            
        Returns:
            Decimal: Balance amount
        """
        try:
            if not public_key:
                return Decimal('0')

            # Ensure key is decrypted
            if not (isinstance(public_key, str) and len(public_key) == 56 and public_key.startswith('G')):
                try:
                    public_key = self._decrypt_key(public_key)
                except Exception:
                    pass

            # Validate format: Stellar public keys are 56 characters starting with 'G'
            if not (isinstance(public_key, str) and len(public_key) == 56 and public_key.startswith('G')):
                return Decimal('0')

            account = self.server.accounts().account_id(public_key).call()
            balance = Decimal('0')
            
            for bal in account.get('balances', []):
                if asset_code == 'XLM' and bal.get('asset_type') == 'native':
                    balance = Decimal(str(bal.get('balance', '0')))
                    break
                elif bal.get('asset_code') == asset_code:
                    balance = Decimal(str(bal.get('balance', '0')))
                    break
            
            return balance
        except NotFoundError:
            return Decimal('0')
        except Exception as e:
            if 'status_code=404' in str(e) or '404' in str(e):
                return Decimal('0')
            raise Exception(f"Error getting balance: {str(e)}")
    
    def get_balance_usd(self, public_key, asset_code='XLM'):
        """
        Get balance in USD equivalent
        
        Args:
            public_key: Wallet public key
            asset_code: Asset code (default: 'XLM')
            
        Returns:
            dict: {
                'balance': Decimal,  # Original balance
                'balance_usd': Decimal,  # USD equivalent
                'asset': str,  # Asset code
                'usd_rate': Decimal  # Exchange rate used
            }
        """
        try:
            balance = self.get_balance(public_key, asset_code)
            
            # Get XLM to USD exchange rate
            # Using a simple API call (you can use CoinGecko, CoinMarketCap, etc.)
            usd_rate = self._get_xlm_usd_rate()
            
            balance_usd = balance * usd_rate
            
            return {
                'balance': balance,
                'balance_usd': balance_usd,
                'asset': asset_code,
                'usd_rate': usd_rate
            }
        except Exception as e:
            raise Exception(f"Error getting USD balance: {str(e)}")
    
    def _get_xlm_usd_rate(self):
        """
        Get XLM to USD exchange rate
        
        Returns:
            Decimal: Exchange rate
        """
        try:
            # Using CoinGecko API (free tier, no API key required)
            response = requests.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies=usd',
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return Decimal(str(data.get('stellar', {}).get('usd', 0.1)))  # Default to 0.1 if not found
            else:
                # Fallback rate
                return Decimal('0.1')
        except Exception as e:
            # Fallback rate if API fails
            return Decimal('0.1')
    
    def get_fees(self):
        """
        Get current network fees
        
        Returns:
            dict: {
                'min_fee': int,  # Minimum fee in stroops (1 XLM = 10,000,000 stroops)
                'max_fee': int,  # Maximum fee
                'mode_fee': int,  # Mode (most common) fee
                'p10_fee': int,  # 10th percentile fee
                'p20_fee': int,  # 20th percentile fee
                'p30_fee': int,  # 30th percentile fee
                'p40_fee': int,  # 40th percentile fee
                'p50_fee': int,  # 50th percentile fee
                'p60_fee': int,  # 60th percentile fee
                'p70_fee': int,  # 70th percentile fee
                'p80_fee': int,  # 80th percentile fee
                'p90_fee': int,  # 90th percentile fee
                'p95_fee': int,  # 95th percentile fee
                'p99_fee': int,  # 99th percentile fee
                'ledger_capacity_usage': float,  # Network capacity usage
                'last_ledger': int,  # Last ledger sequence
                'last_ledger_base_fee': int  # Base fee for last ledger
            }
        """
        try:
            fee_stats = self.server.fee_stats().call()
            
            return {
                'min_fee': int(fee_stats.get('min', 100)),
                'max_fee': int(fee_stats.get('max', 10000)),
                'mode_fee': int(fee_stats.get('mode', 100)),
                'p10_fee': int(fee_stats.get('p10', 100)),
                'p20_fee': int(fee_stats.get('p20', 100)),
                'p30_fee': int(fee_stats.get('p30', 100)),
                'p40_fee': int(fee_stats.get('p40', 100)),
                'p50_fee': int(fee_stats.get('p50', 100)),
                'p60_fee': int(fee_stats.get('p60', 100)),
                'p70_fee': int(fee_stats.get('p70', 100)),
                'p80_fee': int(fee_stats.get('p80', 100)),
                'p90_fee': int(fee_stats.get('p90', 100)),
                'p95_fee': int(fee_stats.get('p95', 100)),
                'p99_fee': int(fee_stats.get('p99', 100)),
                'ledger_capacity_usage': float(fee_stats.get('ledger_capacity_usage', 0)),
                'last_ledger': int(fee_stats.get('last_ledger', 0)),
                'last_ledger_base_fee': int(fee_stats.get('last_ledger_base_fee', 100))
            }
        except Exception as e:
            raise Exception(f"Error getting fees: {str(e)}")
    
    def sweep_funds(self, user_id, asset='XLM', chain='XLM', destination_wallet=None):
        """
        Sweep all funds from a user's wallet to central wallet
        
        Args:
            user_id: User ID
            asset: Asset type (default: 'XLM')
            chain: Chain type (default: 'XLM')
            destination_wallet: Optional destination wallet (defaults to central wallet)
            
        Returns:
            dict: {
                'status': bool,
                'transaction_hash': str,
                'amount_swept': Decimal,
                'fee_paid': Decimal,
                'from_wallet': str,
                'to_wallet': str
            }
        """
        try:
            # Get source wallet keypair
            source_keypair = self.get_wallet_keypair(user_id, asset, chain)
            source_account = source_keypair.public_key
            
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
            
            # Get source account info
            try:
                source_account_obj = self.server.load_account(source_account)
            except NotFoundError:
                raise Exception(f"Source account {source_account} not found on network")
            
            # Get current balance
            balance = self.get_balance(source_account, asset)
            
            if balance <= 0:
                raise Exception("No funds to sweep")
            
            # Get fees
            fees = self.get_fees()
            # Use p50 (median) fee for transaction
            fee = fees.get('p50_fee', 100)
            
            # Calculate amount to send (balance minus fee)
            # Reserve minimum balance for account (0.5 XLM for testnet, 1 XLM for mainnet)
            min_reserve = Decimal('0.5') if self.network == 'testnet' else Decimal('1.0')
            fee_decimal = Decimal(str(fee)) / Decimal('10000000')  # Convert stroops to XLM
            
            # If balance is less than minimum reserve + fee, can't sweep
            if balance < (min_reserve + fee_decimal):
                raise Exception(f"Insufficient balance to sweep. Minimum required: {min_reserve + fee_decimal} XLM")
            
            # Amount to send (all balance minus fee and minimum reserve)
            amount_to_send = balance - fee_decimal - min_reserve
            
            # Build transaction
            transaction = (
                TransactionBuilder(
                    source_account=source_account_obj,
                    network_passphrase=self.network_passphrase,
                    base_fee=fee
                )
                .add_text_memo(f"Sweep from {source_account}")
                .append_payment_op(
                    destination=destination_wallet,
                    amount=str(amount_to_send),
                    asset=Asset.native() if asset == 'XLM' else Asset(asset, issuer="")
                )
                .set_timeout(300)  # 5 minutes
                .build()
            )
            
            # Sign transaction
            transaction.sign(source_keypair)
            
            # Submit transaction
            response = self.server.submit_transaction(transaction)
            
            if response.get('successful'):
                return {
                    'status': True,
                    'transaction_hash': response.get('hash'),
                    'amount_swept': amount_to_send,
                    'fee_paid': fee_decimal,
                    'from_wallet': source_account,
                    'to_wallet': destination_wallet
                }
            else:
                raise Exception(f"Transaction failed: {response.get('extras', {}).get('result_codes', {})}")
                
        except Exception as e:
            raise Exception(f"Error sweeping funds: {str(e)}")


# Backward compatibility function
def generate_stellar_wallet(user_id, asset='XLM', chain='XLM'):
    """Backward compatibility function - creates StellarWallet instance and generates wallet"""
    wallet = StellarWallet()
    return wallet.generate_wallet(user_id, asset, chain)
