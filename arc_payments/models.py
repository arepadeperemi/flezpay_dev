"""
Arc USDC Payment models.

Three models:
  ArcPaymentSession  — one per checkout session
  ArcUSDCTransfer    — one per on-chain Transfer event (immutable audit record)
  ArcIndexerState    — one per network (block cursor for recovery scanner)
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone


def _payment_id():
    return f"PAY-{uuid.uuid4().hex[:12].upper()}"


class ArcPaymentSession(models.Model):
    STATUS_CREATED = 'created'
    STATUS_AWAITING = 'awaiting_payment'
    STATUS_DETECTED = 'detected'
    STATUS_PAID = 'paid'
    STATUS_UNDERPAID = 'underpaid'
    STATUS_OVERPAID = 'overpaid'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_CREATED, 'Created'),
        (STATUS_AWAITING, 'Awaiting Payment'),
        (STATUS_DETECTED, 'Detected'),
        (STATUS_PAID, 'Paid'),
        (STATUS_UNDERPAID, 'Underpaid'),
        (STATUS_OVERPAID, 'Overpaid'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED, 'Failed'),
    ]

    # Identifiers
    payment_id = models.CharField(
        max_length=50, unique=True, default=_payment_id,
        db_index=True, help_text="Human-readable payment ID (PAY-xxxxx)"
    )
    invoice = models.ForeignKey(
        'api.UserInvoices', on_delete=models.CASCADE,
        related_name='arc_payments', null=True, blank=True
    )
    store = models.ForeignKey(
        'api.BusinessDetails', on_delete=models.CASCADE,
        related_name='arc_payments'
    )
    merchant = models.ForeignKey(
        'api.UserSecure', on_delete=models.CASCADE,
        related_name='arc_payments'
    )

    # Network
    network = models.CharField(max_length=50, default='arc-testnet')
    chain_id = models.BigIntegerField(default=5042002)
    token = models.CharField(max_length=20, default='USDC')
    token_contract = models.CharField(max_length=42)

    # Amounts — always use Decimal for money
    order_currency = models.CharField(max_length=10, default='NGN')
    order_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    payment_currency = models.CharField(max_length=10, default='USDC')
    payment_amount = models.DecimalField(
        max_digits=20, decimal_places=6, default=0,
        help_text="Expected USDC amount (locked at session creation)"
    )
    estimated_sweep_fee = models.DecimalField(
        max_digits=20, decimal_places=6, default=0,
        help_text="Estimated gas fee to sweep, converted to USDC"
    )
    fee_buffer = models.DecimalField(
        max_digits=20, decimal_places=6, default=0,
        help_text="Safety buffer added to the sweep fee (USDC)"
    )
    arc_total_amount = models.DecimalField(
        max_digits=20, decimal_places=6, default=0,
        help_text="payment_amount + estimated_sweep_fee + fee_buffer"
    )
    exchange_rate = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True,
        help_text="NGN/USDC rate at time of session creation"
    )
    rate_timestamp = models.DateTimeField(null=True, blank=True)
    received_amount = models.DecimalField(
        max_digits=20, decimal_places=6, default=Decimal('0'),
        help_text="Total USDC received so far (sum of all matching transfers)"
    )

    # Wallet
    deposit_address = models.CharField(
        max_length=42, db_index=True,
        help_text="Unique EVM deposit address for this payment"
    )
    derivation_index = models.PositiveIntegerField(
        help_text="BIP-44 derivation index used to generate deposit_address"
    )
    wallet_identifier = models.CharField(
        max_length=100, default='arc-hd-wallet',
        help_text="Wallet account identifier"
    )

    # Status
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_CREATED,
        db_index=True
    )
    is_overpaid = models.BooleanField(default=False)

    # Blockchain confirmation
    tx_hash = models.CharField(max_length=66, null=True, blank=True)
    block_number = models.BigIntegerField(null=True, blank=True)
    log_index = models.IntegerField(null=True, blank=True)

    # Timestamps
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    detected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Arc Payment Session'
        verbose_name_plural = 'Arc Payment Sessions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['deposit_address', 'status']),
            models.Index(fields=['invoice', 'status']),
        ]

    def __str__(self):
        return f"{self.payment_id} [{self.status}] {self.payment_amount} USDC"

    @property
    def is_active(self):
        """
        A session is still active if it can still receive a payment.
        Includes AWAITING, DETECTED, UNDERPAID states.
        Excludes PAID, CANCELLED, FAILED, EXPIRED.
        """
        active_statuses = (
            self.STATUS_CREATED,
            self.STATUS_AWAITING,
            self.STATUS_DETECTED,
            self.STATUS_UNDERPAID,
        )
        return (
            self.status in active_statuses
            and timezone.now() < self.expires_at
        )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class ArcUSDCTransfer(models.Model):
    """
    Immutable record of an on-chain USDC Transfer event.
    Never deleted — permanent financial audit trail.
    """
    chain_id = models.BigIntegerField(default=5042002)
    network = models.CharField(max_length=50, default='arc-testnet')
    tx_hash = models.CharField(max_length=66, db_index=True)
    log_index = models.IntegerField()
    block_number = models.BigIntegerField(db_index=True)
    from_address = models.CharField(max_length=42, db_index=True)
    to_address = models.CharField(max_length=42, db_index=True)
    amount_raw = models.BigIntegerField(help_text="Raw uint256 value from Transfer log")
    amount = models.DecimalField(
        max_digits=20, decimal_places=6,
        help_text="USDC amount (amount_raw / 10^6)"
    )

    # Payment session (null if address not matched to any active session)
    payment = models.ForeignKey(
        ArcPaymentSession, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transfers'
    )

    # Processing state
    processed = models.BooleanField(default=False)
    is_late_payment = models.BooleanField(
        default=False,
        help_text="True if transfer arrived after session expiry"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Arc USDC Transfer'
        verbose_name_plural = 'Arc USDC Transfers'
        ordering = ['-block_number', '-log_index']
        # Core idempotency constraint — prevents duplicate processing
        unique_together = [['chain_id', 'tx_hash', 'log_index']]
        indexes = [
            models.Index(fields=['to_address', 'processed']),
            models.Index(fields=['payment', 'processed']),
        ]

    def __str__(self):
        return f"Transfer {self.tx_hash[:12]}... → {self.to_address[:10]}... ({self.amount} USDC)"


class ArcIndexerState(models.Model):
    """
    Block cursor for the Arc recovery scanner.
    One row per network.
    """
    network = models.CharField(max_length=50, unique=True)
    last_processed_block = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Arc Indexer State'

    def __str__(self):
        return f"{self.network}: block {self.last_processed_block}"
