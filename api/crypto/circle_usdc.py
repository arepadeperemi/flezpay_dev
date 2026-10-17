import requests
import json
import uuid
import os
import base64
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from datetime import datetime
from dotenv import load_dotenv
from api.models import CryptoLedger, UserSecure, CryptoLedgerSweepWallet
from api.external.encryption import Encryption

# Always import crypto libraries for ciphertext generation
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

# Load environment variables from .env file
load_dotenv()

cipher = Encryption()

# Circle USDC configuration
CIRCLE_API_KEY = os.getenv('CIRCLE_USDC_API_KEY', os.getenv('CIRCLE_USDC_TESTNET', ''))
CIRCLE_BASE_URL = os.getenv('CIRCLE_BASE_URL', 'https://api.circle.com/v1')
HEX_ENCODED_ENTITY_SECRET = os.getenv('HEX_ENCODED_ENTITY_SECRET_KEY', '')

# Supported networks mapping
SUPPORTED_NETWORKS = {
    'ETH': 'ETH',
    'MATIC': 'MATIC',
    'SOL': 'SOL',  # For testnet, use SOL-DEVNET
    'SOL-DEVNET': 'SOL-DEVNET',
    'MATIC-AMOY': 'MATIC-AMOY',
    'ARB': 'ARB',
    'AVAX': 'AVAX',
    'BASE': 'BASE',
}

# Network to asset mapping
NETWORK_TO_ASSET = {
    'ETH': 'USDC',
    'MATIC': 'USDC',
    'SOL': 'USDC',
    'ARB': 'USDC',
    'AVAX': 'USDC',
    'BASE': 'USDC',
}


def uuid7str():
    """Generate UUID7 string - using uuid4 as fallback if uuid7 not available"""
    if hasattr(uuid, 'uuid7'):
        return str(uuid.uuid7())
    try:
        from uuid_extensions import uuid7str as _uuid7str
        return _uuid7str()
    except ImportError:
        return str(uuid.uuid4())


class CircleUSDC:
    """Class for managing Circle USDC wallet operations using direct API calls"""
    
    def __init__(self, api_key=None, base_url=None):
        """
        Initialize Circle USDC wallet handler
        
        Args:
            api_key: Circle API key (defaults to environment variable)
            base_url: Circle API base URL (defaults to environment variable)
        """
        # Get API key - use CIRCLE_USDC_TESTNET as per helper script
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv('CIRCLE_USDC_TESTNET') or os.getenv('CIRCLE_USDC_API_KEY') or ''
        
        self.BASE_URL = base_url or os.getenv('CIRCLE_BASE_URL', 'https://api.circle.com/v1')
        self.base_url = self.BASE_URL  # Keep both for compatibility
        self.hex_encoded_entity_secret = os.getenv('HEX_ENCODED_ENTITY_SECRET_KEY', '')
        
        if not self.api_key:
            raise Exception("Circle API key not configured. Set CIRCLE_USDC_TESTNET or CIRCLE_USDC_API_KEY environment variable.")
        if not self.hex_encoded_entity_secret:
            raise Exception("Entity secret not configured. Set HEX_ENCODED_ENTITY_SECRET_KEY environment variable.")
        
        
        self.headers = {
            "X-Request-Id": uuid7str(),
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def __createPublicKey(self):
        """Get Circle public key for encryption (matches helper script)"""
        try:
            url = "https://api.circle.com/v1/w3s/config/entity/publicKey"
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.ok:
                json_response = response.json()
                return json_response['data']['publicKey']
            else:
                raise Exception({'success': False, "message": str(response.text)})
        except requests.RequestException as e:
            raise Exception({'success': False, "message": str(e)})
    
    def __generateCiphertextEntity(self):
        """Generate encrypted entity secret for Circle API (matches helper script exactly)"""
        try:
            # Clean the hex string - remove hyphens, spaces, and other non-hex characters
            # This handles both UUID format (with hyphens) and pure hex format
            hex_clean = ''.join(c for c in self.hex_encoded_entity_secret if c in '0123456789abcdefABCDEF')
            
            if len(hex_clean) != 64:
                raise Exception(f"Invalid entity secret length. Expected 64 hex characters, got {len(hex_clean)}. Original length: {len(self.hex_encoded_entity_secret)}")
            
            # Convert hex string to bytes
            entity_secret = bytes.fromhex(hex_clean)
            
            if len(entity_secret) != 32:
                raise Exception(f"Invalid entity secret byte length. Expected 32 bytes, got {len(entity_secret)}")
            
            public_key = RSA.importKey(self.__createPublicKey())
            cipher_rsa = PKCS1_OAEP.new(key=public_key, hashAlgo=SHA256)
            encrypted_data = cipher_rsa.encrypt(entity_secret)

            # encode to base64
            encrypted_data_base64 = base64.b64encode(encrypted_data)
            ciphertext = encrypted_data_base64.decode()
            
            return ciphertext
        except Exception as e:
            raise Exception({'success': False, "message": str(e)})
    
    def _generate_ciphertext_entity(self):
        """Alias for __generateCiphertextEntity for backward compatibility"""
        return self.__generateCiphertextEntity()
    
    def createPublicKey(self):
        """Alias for __createPublicKey for backward compatibility"""
        return self.__createPublicKey()
    
    def createWalletSet(self):
        """Create a new wallet set using direct API calls (matches helper script)"""
        try:
            ciphertext = self.__generateCiphertextEntity()
            
            url = "https://api.circle.com/v1/w3s/developer/walletSets"
            payload = {
                "entitySecretCiphertext": ciphertext,
                "idempotencyKey": uuid7str()
            }

            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.ok:
                json_response = response.json()
                wallet_set_id = json_response['data']['walletSet']['id']
                return wallet_set_id
            else:
                error_response = response.json() if response.content else {}
                error_code = error_response.get('code', 'N/A')
                error_msg = error_response.get('message', response.text if not error_response else 'Unknown error')

                # Check for specific error codes
                if error_code == 156013:
                    # Entity secret is invalid - likely not registered
                    raise Exception(
                        f"Entity secret is invalid or not registered with Circle.\n\n"
                        f"Error Code: {error_code}\n"
                        f"Error Message: {error_msg}\n\n"
                        f"To fix this:\n"
                        f"1. Make sure your entity secret is registered with Circle\n"
                        f"2. Run the registration script: python register_circle_entity_secret.py\n"
                        f"3. Or register via Circle's Developer Console\n"
                        f"4. Verify your HEX_ENCODED_ENTITY_SECRET_KEY in .env matches the registered secret\n\n"
                        f"Entity secret being used: {self.hex_encoded_entity_secret[:8]}...{self.hex_encoded_entity_secret[-8:]}\n"
                        f"Reference: https://developers.circle.com/wallets/dev-controlled/register-entity-secret#python"
                    )
                elif error_code == 156016:
                    # Entity secret not set
                    raise Exception(
                        f"Entity secret has not been registered with Circle.\n\n"
                        f"Error Code: {error_code}\n"
                        f"Error Message: {error_msg}\n\n"
                        f"Please register your entity secret by running:\n"
                        f"  python register_circle_entity_secret.py\n\n"
                        f"Reference: https://developers.circle.com/wallets/dev-controlled/register-entity-secret#python"
                    )
                else:
                    raise Exception(f"Failed to create wallet set: {error_msg} (Error Code: {error_code})")
        except requests.RequestException as e:
            raise Exception(f"Exception when calling WalletSetsApi->get_wallet_sets: {str(e)}")
        except Exception as e:
            raise
    
    def _create_wallet_set(self):
        """Internal method to create wallet set (alias for createWalletSet)"""
        return self.createWalletSet()
    
    def create_wallet(self, wallet_type="dynamic", chain=None):
        """
        Create a wallet using direct API calls (matches helper script)
        
        Args:
            wallet_type: "dynamic" or "static" (default: "dynamic")
            chain: Chain name for dynamic wallets (required for dynamic)
            
        Returns:
            dict: {
                "wallet_set_id": str,
                "wallet": dict
            }
        """
        try:
            if wallet_type == "dynamic":
                if chain is None:
                    raise Exception("Error: Specify a chain")
                blockchain = [f"{chain}"]
            else:
                if wallet_type != "static":
                    raise Exception("Wallet type must be 'dynamic' or 'static")
                blockchain = ['ETH', 'MATIC', 'SOL', 'ARB']
            
            wallet_set_id = self.createWalletSet()
            url = f"{self.BASE_URL}/w3s/developer/wallets"
            payload = {
                "idempotencyKey": uuid7str(),
                "blockchains": blockchain,
                "accountType": 'EOA',
                "count": 1,
                "entitySecretCiphertext": self.__generateCiphertextEntity(),
                "walletSetId": wallet_set_id
            }
            response = requests.request("post", url=url, json=payload, headers=self.headers, timeout=30)
            if response.status_code == 201:
                return {
                    "wallet_set_id": wallet_set_id,
                    "wallet": response.json()
                }
            else:
                error_msg = response.json().get('message', 'Unknown error') if response.content else response.text
                raise Exception(f"Operation error: {error_msg}")
        except (Exception, requests.RequestException) as exp:
            raise Exception(str(exp))
    
    def _get_or_create_wallet_set_id(self, user):
        """
        Get existing wallet set ID for user or create a new one
        Ensures each user has only one wallet set ID
        
        Args:
            user: UserSecure instance
            
        Returns:
            str: Wallet set ID
        """
        # Check if user already has any Circle USDC wallet (any chain)
        existing_wallet = CryptoLedger.objects.filter(
            user=user,
            asset='USDC'
        ).first()
        
        if existing_wallet:
            # Reuse existing wallet set ID
            wallet_set_id = self._decrypt_key(existing_wallet.private_key)
            return wallet_set_id
        
        # Create new wallet set for this user
        wallet_set_id = self._create_wallet_set()
        return wallet_set_id
    
    def generate_wallet(self, user_id, asset='USDC', chain='ETH'):
        """
        Generate a new Circle USDC wallet or return existing one
        
        Args:
            user_id: User ID
            asset: Asset type (default: 'USDC')
            chain: Chain/network (default: 'ETH')
            
        Returns:
            dict: {
                'wallet_id': str,
                'address': str,
                'blockchain': str,
                'wallet_set_id': str
            }
        """
        try:
            # Get the UserSecure instance
            user = UserSecure.objects.get(user_id=user_id)
            
            # Normalize chain name
            chain_normalized = chain.upper()
            if chain_normalized not in SUPPORTED_NETWORKS:
                raise Exception(f"Unsupported chain: {chain}. Supported chains: {', '.join(SUPPORTED_NETWORKS.keys())}")
            
            # Check if wallet already exists for this user, asset, and chain
            existing_wallet = CryptoLedger.objects.filter(
                user=user,
                asset=asset,
                asset_chain=chain_normalized
            ).first()
            
            if existing_wallet:
                # Return existing wallet info
                wallet_id = self._decrypt_key(existing_wallet.public_key)  # Stored as wallet_id
                wallet_set_id = self._decrypt_key(existing_wallet.private_key)  # Stored as wallet_set_id
                
                # Get wallet details from Circle
                wallet_info = self.get_wallet(wallet_id)
                
                return {
                    'wallet_id': wallet_id,
                    'address': wallet_info['data']['wallet']['address'],
                    'blockchain': wallet_info['data']['wallet']['blockchain'],
                    'wallet_set_id': wallet_set_id
                }
            
            # Get or create wallet set ID for this user (ensures one wallet set per user)
            wallet_set_id = self._get_or_create_wallet_set_id(user)
            circle_chain = SUPPORTED_NETWORKS[chain_normalized]
            
            url = f"{self.base_url}/w3s/developer/wallets"
            payload = {
                "idempotencyKey": uuid7str(),
                "blockchains": [circle_chain],
                "accountType": 'EOA',
                "count": 1,
                "entitySecretCiphertext": self._generate_ciphertext_entity(),
                "walletSetId": wallet_set_id
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 201:
                json_response = response.json()
                wallet_data = json_response['data']['wallets'][0]
                wallet_id = wallet_data['id']
                wallet_address = wallet_data['address']
                blockchain = wallet_data['blockchain']
                
                # Save to CryptoLedger model
                ledger_entry = CryptoLedger(
                    user=user,
                    asset=asset,
                    asset_chain=chain_normalized,
                    private_key=cipher.encrypt(wallet_set_id),  # Store wallet_set_id
                    public_key=cipher.encrypt(wallet_id),  # Store wallet_id
                    balance=0.0
                )
                ledger_entry.save()
                
                return {
                    'wallet_id': wallet_id,
                    'address': wallet_address,
                    'blockchain': blockchain,
                    'wallet_set_id': wallet_set_id
                }
            else:
                error_msg = response.json().get('message', 'Unknown error') if response.content else response.text
                raise Exception(f"Failed to create wallet: {error_msg}")
                
        except UserSecure.DoesNotExist:
            raise Exception(f"User not found. Login and try again or contact support")
        except Exception as e:
            raise Exception(f"Error creating wallet: {str(e)}")
    
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
    
    def get_wallet_keypair(self, user_id, asset='USDC', chain='ETH'):
        """
        Get wallet ID and wallet set ID for a user's wallet
        
        Args:
            user_id: User ID
            asset: Asset type
            chain: Chain type
            
        Returns:
            tuple: (wallet_id, wallet_set_id)
        """
        try:
            user = UserSecure.objects.get(user_id=user_id)
            wallet = CryptoLedger.objects.filter(
                user=user,
                asset=asset,
                asset_chain=chain.upper()
            ).first()
            
            if not wallet:
                raise Exception(f"Wallet not found for user {user_id} on chain {chain}")
            
            wallet_id = self._decrypt_key(wallet.public_key)
            
            # Get wallet_set_id from this wallet or any other USDC wallet for this user
            # (since all wallets for a user share the same wallet_set_id)
            wallet_set_id = self._decrypt_key(wallet.private_key)
            
            return wallet_id, wallet_set_id
            
        except UserSecure.DoesNotExist:
            raise Exception(f"User not found")
        except Exception as e:
            raise Exception(f"Error getting wallet keypair: {str(e)}")
    
    def get_user_wallet_set_id(self, user_id):
        """
        Get the wallet set ID for a user (shared across all their USDC wallets)
        
        Args:
            user_id: User ID
            
        Returns:
            str: Wallet set ID
        """
        try:
            user = UserSecure.objects.get(user_id=user_id)
            
            # Get any USDC wallet for this user to retrieve wallet_set_id
            wallet = CryptoLedger.objects.filter(
                user=user,
                asset='USDC'
            ).first()
            
            if not wallet:
                raise Exception(f"No Circle USDC wallet found for user {user_id}")
            
            wallet_set_id = self._decrypt_key(wallet.private_key)
            return wallet_set_id
            
        except UserSecure.DoesNotExist:
            raise Exception(f"User not found")
        except Exception as e:
            raise Exception(f"Error getting wallet set ID: {str(e)}")
    
    def get_wallet(self, wallet_id):
        """
        Get wallet details from Circle (matches helper script)
        
        Args:
            wallet_id: Circle wallet ID
            
        Returns:
            dict: Wallet information
        """
        try:
            url = f"{self.BASE_URL}/w3s/wallets/{wallet_id}"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                transfer_info = response.json()
                return transfer_info
            else:
                raise Exception(f"Failed to get wallet: {response.text}")
        except (Exception, requests.RequestException) as e:
            raise Exception(str(e))
    
    def get_wallet_balance(self, wallet_id):
        """
        Get total balance of a Circle wallet (matches helper script)
        
        Args:
            wallet_id: Circle wallet ID
            
        Returns:
            float: Total balance
        """
        try:
            url = f"https://api.circle.com/v1/w3s/wallets/{wallet_id}/balances"
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.ok:
                json_response = response.json()
                data = json_response['data']['tokenBalances']
                total_balance = sum(float(token['amount']) for token in data)
                return total_balance
        except requests.RequestException as e:
            raise Exception(f"Could not get wallet balance: {str(e)}")
    
    def get_balance(self, wallet_id, asset_code='USDC'):
        """
        Get balance for a specific asset in a wallet
        
        Args:
            wallet_id: Circle wallet ID
            asset_code: Asset code (default: 'USDC')
            
        Returns:
            Decimal: Balance amount
        """
        try:
            url = f"{self.base_url}/w3s/wallets/{wallet_id}/balances"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.ok:
                json_response = response.json()
                data = json_response.get('data', {}).get('tokenBalances', [])
                
                # Find USDC balance
                for token in data:
                    if token.get('token', {}).get('symbol') == asset_code:
                        return Decimal(str(token.get('amount', 0)))
                
                return Decimal('0')
            else:
                return Decimal('0')
        except Exception as e:
            raise Exception(f"Error getting balance: {str(e)}")
    
    def get_balance_usd(self, wallet_id, asset_code='USDC'):
        """
        Get balance in USD equivalent (USDC is already USD-pegged, so 1:1)
        
        Args:
            wallet_id: Circle wallet ID
            asset_code: Asset code (default: 'USDC')
            
        Returns:
            dict: {
                'balance': Decimal,  # Original balance
                'balance_usd': Decimal,  # USD equivalent (same as balance for USDC)
                'asset': str,  # Asset code
                'usd_rate': Decimal  # Exchange rate (1.0 for USDC)
            }
        """
        try:
            balance = self.get_balance(wallet_id, asset_code)
            
            # USDC is pegged to USD, so rate is 1.0
            usd_rate = Decimal('1.0')
            balance_usd = balance * usd_rate
            
            return {
                'balance': balance,
                'balance_usd': balance_usd,
                'asset': asset_code,
                'usd_rate': usd_rate
            }
        except Exception as e:
            raise Exception(f"Error getting USD balance: {str(e)}")
    
    def send_balance(self, wallet_id, destination_address, amount=None):
        """
        Send balance from wallet to destination (matches helper script)
        
        Args:
            wallet_id: Source wallet ID
            destination_address: Destination address
            amount: Amount to send (default: all balance)
            
        Returns:
            dict: Transaction response
        """
        try:
            if amount is None:
                amount = self.get_wallet_balance(wallet_id)
            url = f"{self.BASE_URL}/w3s/developer/transactions/transfer"
            wallet_info = self.get_wallet(wallet_id)
            blockchain = wallet_info['data']['wallet']['blockchain']
            
            payload = {
                "walletId": wallet_id,
                "blockchain": blockchain,
                "feeLevel": "MEDIUM",
                "entitySecretCiphertext": self.__generateCiphertextEntity(),
                "destinationAddress": destination_address,
                "amounts": [f"{amount}"],
                "idempotencyKey": uuid7str()
            }
            response = requests.request("post", url, json=payload, headers=self.headers, timeout=30)
            if response.status_code == 201:
                return response.json()
            else:
                error_msg = response.json().get('message', 'Unknown error') if response.content else response.text
                raise Exception(f"Error sending trx: {error_msg}")
        except (Exception, requests.RequestException) as e:
            raise Exception(str(e))
    
    def get_total_fees(self, wallet_id, destination_address, amount):
        """
        Get total fees for a transaction (matches helper script)
        
        Args:
            wallet_id: Source wallet ID
            destination_address: Destination address
            amount: Amount to send
            
        Returns:
            float: Total fee in USD
        """
        try:
            dest_wallet = self.get_wallet(wallet_id)
            url = f"{self.BASE_URL}/w3s/transactions/transfer/estimateFee"
            blockchain = dest_wallet['data']['wallet']['blockchain']
            source_address = dest_wallet['data']['wallet']['address']
            
            payload = {
                "blockchain": blockchain,
                "sourceAddress": source_address,
                "destinationAddress": destination_address,
                "amounts": [f'{amount}']
            }
            response = requests.request("post", url, json=payload, headers=self.headers, timeout=30)
            if response.status_code == 200:
                json_response = response.json()
                fee = json_response['data']['medium']
                networkFee = float(fee['networkFee'])
                base_fee = float(fee['baseFee'])
                gas_price = base_fee + networkFee
                total_fee = gas_price
                # Convert to USDC
                price_url = f"https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
                resp = requests.get(price_url, timeout=10)
                if resp.status_code == 200:
                    usdc_price = resp.json()['solana']['usd']
                    return total_fee * usdc_price
                else:
                    raise Exception(resp.text)
            else:
                raise Exception(response.text)
        except (Exception, requests.RequestException) as exp:
            raise Exception(str(exp))
    
    def get_fees(self, wallet_id, destination_address, amount):
        """
        Get estimated fees for a transaction
        
        Args:
            wallet_id: Source wallet ID
            destination_address: Destination address
            amount: Amount to send
            
        Returns:
            dict: {
                'network_fee': Decimal,
                'base_fee': Decimal,
                'total_fee': Decimal,
                'total_fee_usd': Decimal
            }
        """
        try:
            wallet_info = self.get_wallet(wallet_id)
            blockchain = wallet_info['data']['wallet']['blockchain']
            source_address = wallet_info['data']['wallet']['address']
            
            url = f"{self.base_url}/w3s/transactions/transfer/estimateFee"
            payload = {
                "blockchain": blockchain,
                "sourceAddress": source_address,
                "destinationAddress": destination_address,
                "amounts": [str(amount)]
            }
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                json_response = response.json()
                fee = json_response['data']['medium']
                network_fee = Decimal(str(fee.get('networkFee', 0)))
                base_fee = Decimal(str(fee.get('baseFee', 0)))
                total_fee = network_fee + base_fee
                
                # Convert to USD equivalent (for native tokens like ETH, MATIC, SOL)
                # For USDC transfers, fees are usually in native token
                total_fee_usd = self._convert_fee_to_usd(blockchain, total_fee)
                
                return {
                    'network_fee': network_fee,
                    'base_fee': base_fee,
                    'total_fee': total_fee,
                    'total_fee_usd': total_fee_usd,
                    'blockchain': blockchain
                }
            else:
                raise Exception(f"Failed to estimate fees: {response.text}")
        except Exception as e:
            raise Exception(f"Error getting fees: {str(e)}")
    
    def _convert_fee_to_usd(self, blockchain, fee_amount):
        """Convert native token fee to USD"""
        try:
            # Map blockchain to CoinGecko ID
            coin_ids = {
                'ETH': 'ethereum',
                'MATIC': 'matic-network',
                'SOL': 'solana',
                'ARB': 'arbitrum',
                'AVAX': 'avalanche-2',
                'BASE': 'ethereum'  # Base uses ETH
            }
            
            coin_id = coin_ids.get(blockchain)
            if not coin_id:
                return Decimal('0')  # Unknown blockchain
            
            price_url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            resp = requests.get(price_url, timeout=10)
            
            if resp.status_code == 200:
                price_data = resp.json().get(coin_id, {})
                usd_price = Decimal(str(price_data.get('usd', 0)))
                return fee_amount * usd_price
            else:
                return Decimal('0')
        except Exception:
            return Decimal('0')
    
    def sweep_funds(self, user_id, asset='USDC', chain='ETH', destination_wallet=None):
        """
        Sweep all funds from a user's wallet to central wallet
        
        Args:
            user_id: User ID
            asset: Asset type (default: 'USDC')
            chain: Chain type (default: 'ETH')
            destination_wallet: Optional destination wallet (defaults to central wallet)
            
        Returns:
            dict: {
                'status': bool,
                'transaction_id': str,
                'amount_swept': Decimal,
                'fee_paid': Decimal,
                'from_wallet': str,
                'to_wallet': str
            }
        """
        try:
            # Get wallet IDs
            wallet_id, wallet_set_id = self.get_wallet_keypair(user_id, asset, chain)
            
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
            balance = self.get_balance(wallet_id, asset)
            
            if balance <= 0:
                return {
                    'status': False,
                    'message': 'No funds to sweep',
                    'amount_swept': Decimal('0'),
                    'from_wallet': wallet_id,
                    'to_wallet': destination_wallet
                }
            
            # Send all balance
            result = self.send_balance(wallet_id, destination_wallet, float(balance))
            
            # Extract transaction ID from result
            transaction_id = result.get('data', {}).get('id', '') if isinstance(result, dict) else ''
            
            # Get fees (estimate)
            fees = self.get_fees(wallet_id, destination_wallet, float(balance))
            
            return {
                'status': True,
                'transaction_id': transaction_id,
                'amount_swept': balance,
                'fee_paid': fees.get('total_fee', Decimal('0')),
                'from_wallet': wallet_id,
                'to_wallet': destination_wallet
            }
            
        except Exception as e:
            raise Exception(f"Error sweeping funds: {str(e)}")


def generate_circle_usdc_wallet(user_id, asset='USDC', chain='ETH'):
    """Backward compatibility function - creates CircleUSDC instance and generates wallet"""
    wallet = CircleUSDC()
    return wallet.generate_wallet(user_id, asset, chain)
