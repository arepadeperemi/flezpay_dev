"""
Arc HD Wallet Service.

Derives unique EVM deposit addresses from a BIP-44 HD wallet.
The master seed NEVER leaves the server.

Architecture:
    ARC_HD_WALLET_SEED (env, Fernet-encrypted) → decrypt → BIP-39 mnemonic
        → BIP-44 derivation path m/44'/60'/0'/0/{index}
        → Arc deposit address (EVM-compatible)
"""
import logging
import os
from typing import Tuple

from django.conf import settings
# pyrefly: ignore [missing-import]
from eth_account import Account

from api.external.encryption import Encryption

logger = logging.getLogger('arc_payments.wallet')

# Enable eth_account HD wallet support
Account.enable_unaudited_hdwallet_features()

_cipher = Encryption()

# BIP-44 base path for Ethereum/EVM
_BASE_PATH = "m/44'/60'/0'/0"


def _load_or_create_seed() -> str:
    """
    Load the HD wallet mnemonic from ARC_HD_WALLET_SEED (Fernet-encrypted).
    If not set or decryption fails, generate a new mnemonic, log it once,
    and return it. The operator MUST copy it to ARC_HD_WALLET_SEED immediately.
    """
    raw = os.getenv('ARC_HD_WALLET_SEED', '').strip()
    if raw:
        try:
            decrypted = _cipher.decrypt(raw.encode())
            if decrypted:
                return decrypted
        except Exception:
            pass  # fall through to generate

    # Auto-generate on first run
    from mnemonic import Mnemonic
    mnemo = Mnemonic("english")
    new_mnemonic = mnemo.generate(strength=256)
    encrypted = _cipher.encrypt(new_mnemonic).decode()

    logger.critical(
        "\n"
        "╔══════════════════════════════════════════════════════════════════╗\n"
        "║       ARC HD WALLET SEED GENERATED — ACTION REQUIRED            ║\n"
        "║  Copy the value below into your .env as ARC_HD_WALLET_SEED=     ║\n"
        "║  KEEP THIS SECRET. LOSING IT MEANS LOSING UNSWEPT FUNDS.        ║\n"
        "╚══════════════════════════════════════════════════════════════════╝\n"
        "ARC_HD_WALLET_SEED=%s",
        encrypted,
    )
    return new_mnemonic


# Module-level seed cache (loaded once per process)
_MNEMONIC: str = None


def _get_mnemonic() -> str:
    global _MNEMONIC
    if _MNEMONIC is None:
        _MNEMONIC = _load_or_create_seed()
    return _MNEMONIC


def derive_address(derivation_index: int) -> Tuple[str, str]:
    """
    Derive the EVM deposit address for the given BIP-44 index.

    Args:
        derivation_index: Integer index (0, 1, 2, …)

    Returns:
        (address, derivation_path) — address is checksummed EVM address.
    """
    mnemonic = _get_mnemonic()
    path = f"{_BASE_PATH}/{derivation_index}"
    account = Account.from_mnemonic(mnemonic, account_path=path)
    return account.address, path


def get_next_derivation_index(merchant_id: str) -> int:
    """
    Return the next available derivation index for this merchant.
    Simply counts existing ArcPaymentSessions for the merchant.
    Using a global counter across all merchants is fine since each
    index maps to exactly one deposit address regardless of merchant.
    """
    from arc_payments.models import ArcPaymentSession
    return ArcPaymentSession.objects.count()


def verify_rpc_connection() -> dict:
    """
    Quick health-check: call eth_chainId on the Arc HTTP RPC.
    Returns dict with 'ok', 'chain_id', 'error'.
    """
    import requests
    from arc_payments.config import ARC_RPC_URL, ARC_CHAIN_ID
    try:
        resp = requests.post(
            ARC_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "eth_chainId", "params": []},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        chain_id_hex = result.get('result', '0x0')
        chain_id = int(chain_id_hex, 16)
        ok = (chain_id == ARC_CHAIN_ID)
        return {'ok': ok, 'chain_id': chain_id, 'expected': ARC_CHAIN_ID}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}
