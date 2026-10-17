"""
Central Arc Testnet configuration module.

All values are read from Django settings (which read from .env).
Import from here — never scatter os.getenv('ARC_*') across the codebase.
"""
from django.conf import settings

# ── Network ─────────────────────────────────────────────────────────────────
ARC_ENABLED: bool = getattr(settings, 'ARC_ENABLED', False)
ARC_NETWORK: str = getattr(settings, 'ARC_NETWORK', 'arc-testnet')
ARC_CHAIN_ID: int = getattr(settings, 'ARC_CHAIN_ID', 5042002)
ARC_CHAIN_ID_HEX: str = getattr(settings, 'ARC_CHAIN_ID_HEX', '0x4cef52')

# ── RPC (server-side only — never sent to browser) ──────────────────────────
ARC_RPC_URL: str = getattr(settings, 'ARC_RPC_URL', '')
ARC_WS_URL: str = getattr(settings, 'ARC_WS_URL', '')

# ── USDC Contract ────────────────────────────────────────────────────────────
ARC_USDC_ADDRESS: str = getattr(
    settings, 'ARC_USDC_ADDRESS',
    '0x3600000000000000000000000000000000000000'
).lower()
ARC_USDC_DECIMALS: int = getattr(settings, 'ARC_USDC_DECIMALS', 6)

# keccak256("Transfer(address,address,uint256)")
USDC_TRANSFER_TOPIC: str = (
    '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
)

# ── Explorer ─────────────────────────────────────────────────────────────────
ARC_EXPLORER_URL: str = getattr(
    settings, 'ARC_EXPLORER_URL', 'https://testnet.arcscan.app'
)

# ── Payment session ──────────────────────────────────────────────────────────
ARC_PAYMENT_EXPIRY_MINUTES: int = getattr(settings, 'ARC_PAYMENT_EXPIRY_MINUTES', 15)

# ── Recovery scanner ─────────────────────────────────────────────────────────
ARC_SCANNER_BATCH_SIZE: int = getattr(settings, 'ARC_SCANNER_BATCH_SIZE', 100)
ARC_SCANNER_INTERVAL_SECONDS: int = getattr(settings, 'ARC_SCANNER_INTERVAL_SECONDS', 2)

# ── Fees ─────────────────────────────────────────────────────────────────────
# Additional safety buffer for Arc network sweep fee (in USDC)
ARC_SWEEP_FEE_BUFFER_USDC: float = getattr(settings, 'ARC_SWEEP_FEE_BUFFER_USDC', 0.05)
# Conversion rate if ARC is not 1:1 with USDC (default 1.0 for now)
ARC_TO_USDC_RATE: float = getattr(settings, 'ARC_TO_USDC_RATE', 1.0)


def explorer_tx_url(tx_hash: str) -> str:
    """Return a full block-explorer URL for a transaction hash."""
    return f"{ARC_EXPLORER_URL}/tx/{tx_hash}"
