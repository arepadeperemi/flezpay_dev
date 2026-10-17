"""
Arc USDC Payment Service.

All business logic lives here — views, tasks, and the listener all call this.
Never call models directly from views without going through this service.
"""
import logging
import requests
from decimal import Decimal, ROUND_UP
from typing import Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from arc_payments.config import (
    ARC_CHAIN_ID,
    ARC_NETWORK,
    ARC_PAYMENT_EXPIRY_MINUTES,
    ARC_RPC_URL,
    ARC_SWEEP_FEE_BUFFER_USDC,
    ARC_TO_USDC_RATE,
    ARC_USDC_ADDRESS,
    explorer_tx_url,
)
from arc_payments.models import ArcIndexerState, ArcPaymentSession, ArcUSDCTransfer
from arc_payments.wallet import derive_address, get_next_derivation_index

logger = logging.getLogger('arc_payments.services')


# ── Exchange rate ─────────────────────────────────────────────────────────────

def get_usdc_price_in_currency(currency: str = 'ngn') -> Optional[Decimal]:
    """
    Fetch live USDC price from CoinGecko free API.
    Returns how many units of `currency` equal 1 USDC.
    e.g. for NGN: returns ~1650.0 meaning 1 USDC = ₦1650
    """
    try:
        resp = requests.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': 'usd-coin', 'vs_currencies': currency.lower()},
            timeout=8,
        )
        resp.raise_for_status()
        price = resp.json().get('usd-coin', {}).get(currency.lower())
        if price:
            return Decimal(str(price))
    except Exception as exc:
        logger.warning("CoinGecko rate fetch failed: %s", exc)
    return None


def calculate_usdc_amount(invoice) -> tuple[Decimal, Decimal, Optional[Decimal]]:
    """
    Convert the invoice grand total to USDC.

    Returns:
        (order_amount, usdc_amount, exchange_rate)
        exchange_rate is None if conversion failed (use 1:1 fallback).
    """
    from api.models import UserInvoiceItems
    items = UserInvoiceItems.objects.filter(item_invoice_id=invoice.invoice_id)
    grand_total = sum(item.item_amount * item.item_quantity for item in items)
    order_amount = Decimal(str(grand_total))

    # Determine merchant's currency
    try:
        merchant_currency = (
            invoice.user_id.details.first().currency or 'NGN'
        ).upper()
    except Exception:
        merchant_currency = 'NGN'

    if merchant_currency == 'USD':
        # 1 USDC ≈ 1 USD
        usdc_amount = order_amount.quantize(Decimal('0.000001'), rounding=ROUND_UP)
        return order_amount, usdc_amount, Decimal('1')

    # Fetch live rate
    rate = get_usdc_price_in_currency(merchant_currency)
    if rate and rate > 0:
        usdc_amount = (order_amount / rate).quantize(
            Decimal('0.000001'), rounding=ROUND_UP
        )
        return order_amount, usdc_amount, rate

    # Fallback: assume 1 NGN = 0.00065 USDC (rough peg)
    fallback_rate = Decimal('1650')
    usdc_amount = (order_amount / fallback_rate).quantize(
        Decimal('0.000001'), rounding=ROUND_UP
    )
    logger.warning("Using fallback exchange rate 1 USDC = %s %s", fallback_rate, merchant_currency)
    return order_amount, usdc_amount, fallback_rate


def estimate_arc_sweep_fee_usdc() -> Decimal:
    """
    Estimates the Arc sweep gas fee in USDC.
    Queries the Arc RPC for eth_gasPrice, assumes 100,000 gas for an ERC20 transfer,
    and converts to USDC using ARC_TO_USDC_RATE.
    """
    gas_limit = Decimal('100000') # Typical ERC20 transfer gas limit
    try:
        resp = requests.post(
            ARC_RPC_URL,
            json={"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1},
            timeout=5
        )
        if resp.status_code == 200:
            gas_price_hex = resp.json().get('result', '0x0')
            gas_price_wei = Decimal(int(gas_price_hex, 16))
            
            # gas * gas_price (in Wei) -> ARC (10^18 Wei = 1 ARC)
            fee_arc = (gas_limit * gas_price_wei) / Decimal('1000000000000000000')
            
            # Convert ARC fee to USDC
            fee_usdc = fee_arc * Decimal(str(ARC_TO_USDC_RATE))
            return fee_usdc.quantize(Decimal('0.000001'), rounding=ROUND_UP)
    except Exception as e:
        logger.warning(f"Failed to estimate Arc sweep fee: {e}")
    
    # Fallback if RPC fails: 0.002 USDC (roughly 20 gwei * 100k gas)
    return Decimal('0.002')


# ── Payment session ───────────────────────────────────────────────────────────

def create_or_get_payment_session(invoice, store, merchant) -> ArcPaymentSession:
    """
    Return an existing active Arc payment session for this invoice,
    or create a new one.
    Idempotent: safe to call multiple times.
    """
    # Check for existing active session (or recoverable underpaid session)
    existing = ArcPaymentSession.objects.filter(
        invoice=invoice,
        network=ARC_NETWORK,
        token='USDC',
    ).exclude(
        status__in=[
            ArcPaymentSession.STATUS_EXPIRED,
            ArcPaymentSession.STATUS_CANCELLED,
            ArcPaymentSession.STATUS_FAILED,
            ArcPaymentSession.STATUS_PAID,
        ]
    ).first()

    if existing:
        # Return any existing in-progress session, even if expired (underpaid recovery)
        if existing.is_active:
            logger.info("Returning existing active session %s for invoice %s",
                        existing.payment_id, invoice.invoice_id)
            return existing
        # If underpaid or detected but expired, extend expiry so customer can retry
        if existing.status in [
            ArcPaymentSession.STATUS_UNDERPAID,
            ArcPaymentSession.STATUS_DETECTED,
        ]:
            existing.expires_at = timezone.now() + timezone.timedelta(minutes=ARC_PAYMENT_EXPIRY_MINUTES)
            existing.save(update_fields=['expires_at'])
            logger.info(
                "Extending expiry of underpaid session %s for invoice %s",
                existing.payment_id, invoice.invoice_id
            )
            return existing

    # Create new session
    order_amount, usdc_amount, exchange_rate = calculate_usdc_amount(invoice)
    index = get_next_derivation_index(str(merchant.user_id))
    address, _ = derive_address(index)

    try:
        merchant_currency = (
            merchant.details.first().currency or 'NGN'
        ).upper()
    except Exception:
        merchant_currency = 'NGN'

    expires_at = timezone.now() + timezone.timedelta(minutes=ARC_PAYMENT_EXPIRY_MINUTES)
    
    # Calculate sweep fees
    estimated_sweep_fee = estimate_arc_sweep_fee_usdc()
    fee_buffer = Decimal(str(ARC_SWEEP_FEE_BUFFER_USDC))
    arc_total_amount = usdc_amount + estimated_sweep_fee + fee_buffer

    session = ArcPaymentSession.objects.create(
        invoice=invoice,
        store=store,
        merchant=merchant,
        network=ARC_NETWORK,
        chain_id=ARC_CHAIN_ID,
        token='USDC',
        token_contract=ARC_USDC_ADDRESS,
        order_currency=merchant_currency,
        order_amount=order_amount,
        payment_currency='USDC',
        payment_amount=usdc_amount,
        estimated_sweep_fee=estimated_sweep_fee,
        fee_buffer=fee_buffer,
        arc_total_amount=arc_total_amount,
        exchange_rate=exchange_rate,
        rate_timestamp=timezone.now(),
        deposit_address=address.lower(),
        derivation_index=index,
        wallet_identifier='arc-hd-wallet',
        status=ArcPaymentSession.STATUS_AWAITING,
        expires_at=expires_at,
    )
    logger.info(
        "Created Arc payment session %s: %s USDC total (order: %s, fee: %s, buffer: %s) → %s (expires %s)",
        session.payment_id, arc_total_amount, usdc_amount, estimated_sweep_fee, fee_buffer, address, expires_at
    )
    return session


# ── Event processing ──────────────────────────────────────────────────────────

def process_transfer_event(
    chain_id: int,
    network: str,
    tx_hash: str,
    log_index: int,
    block_number: int,
    from_address: str,
    to_address: str,
    amount_raw: int,
) -> Optional[ArcUSDCTransfer]:
    """
    Process one USDC Transfer log event.
    Idempotent — safe to call multiple times for the same event.
    Returns the ArcUSDCTransfer record, or None if already processed.
    """
    amount = Decimal(str(amount_raw)) / Decimal(10 ** 6)
    to_addr = to_address.lower()
    from_addr = from_address.lower()

    try:
        with transaction.atomic():
            # Idempotency: get or create the transfer record
            transfer, created = ArcUSDCTransfer.objects.get_or_create(
                chain_id=chain_id,
                tx_hash=tx_hash,
                log_index=log_index,
                defaults={
                    'network': network,
                    'block_number': block_number,
                    'from_address': from_addr,
                    'to_address': to_addr,
                    'amount_raw': amount_raw,
                    'amount': amount,
                    'processed': False,
                }
            )

            if not created:
                # Already recorded — skip (duplicate event handling)
                logger.debug(
                    "Duplicate event ignored: tx=%s log=%s", tx_hash, log_index
                )
                return None

            logger.info(
                "USDC transfer detected: %s USDC → %s (tx=%s block=%s)",
                amount, to_addr, tx_hash[:16], block_number,
            )

            # Try to match to an active payment session
            session = (
                ArcPaymentSession.objects
                .select_for_update()
                .filter(
                    deposit_address=to_addr,
                    chain_id=chain_id,
                    token='USDC',
                )
                .exclude(
                    status__in=[
                        ArcPaymentSession.STATUS_PAID,
                        ArcPaymentSession.STATUS_CANCELLED,
                        ArcPaymentSession.STATUS_FAILED,
                        ArcPaymentSession.STATUS_EXPIRED,
                    ]
                )
                .first()
            )

            if not session:
                logger.info(
                    "Transfer %s → %s: no active payment session matched.",
                    tx_hash[:16], to_addr
                )
                transfer.processed = True
                transfer.save(update_fields=['processed'])
                return transfer

            # Link transfer to session
            transfer.payment = session
            now = timezone.now()

            # Late payment check
            if now > session.expires_at and session.status not in [
                ArcPaymentSession.STATUS_AWAITING,
                ArcPaymentSession.STATUS_UNDERPAID,
                ArcPaymentSession.STATUS_DETECTED,
            ]:
                transfer.is_late_payment = True
                transfer.save(update_fields=['payment', 'is_late_payment'])
                logger.warning(
                    "Late payment for session %s (expired at %s)",
                    session.payment_id, session.expires_at
                )
                return transfer

            # Accumulate received amount
            session.received_amount = (
                ArcUSDCTransfer.objects
                .filter(payment=session, processed=True)
                .exclude(id=transfer.id)
                .aggregate(total=models_sum('amount'))['total'] or Decimal('0')
            ) + amount

            # Mark detected
            if session.status not in [
                ArcPaymentSession.STATUS_DETECTED,
                ArcPaymentSession.STATUS_PAID,
            ]:
                session.status = ArcPaymentSession.STATUS_DETECTED
                session.detected_at = now
                session.tx_hash = tx_hash
                session.block_number = block_number
                session.log_index = log_index

            # Validate amount
            expected = session.arc_total_amount
            received = session.received_amount

            if received >= expected:
                session.status = ArcPaymentSession.STATUS_PAID
                session.paid_at = now
                if received > expected:
                    session.is_overpaid = True
                    logger.info(
                        "Overpayment on session %s: expected %s USDC, received %s USDC",
                        session.payment_id, expected, received
                    )
                else:
                    logger.info(
                        "Payment CONFIRMED for session %s: %s USDC",
                        session.payment_id, received
                    )
            else:
                session.status = ArcPaymentSession.STATUS_UNDERPAID
                session.expires_at = timezone.now() + timezone.timedelta(minutes=15)
                logger.info(
                    "Underpayment on session %s: expected %s, received %s (expiry extended to %s)",
                    session.payment_id, expected, received, session.expires_at
                )

            session.save()
            transfer.processed = True
            transfer.save(update_fields=['payment', 'processed', 'is_late_payment'])

            # Finalize invoice if paid
            if session.status == ArcPaymentSession.STATUS_PAID:
                _finalize_invoice(session)
            elif session.status == ArcPaymentSession.STATUS_UNDERPAID:
                try:
                    invoice = session.invoice
                    if invoice and getattr(invoice, 'customer_email', None):
                        from api.functions import send_mail
                        from django.conf import settings
                        remain = session.arc_total_amount - session.received_amount
                        
                        domain = getattr(settings, 'STORE_BASE_DOMAIN', 'localhost:8000')
                        protocol = getattr(settings, 'STORE_PROTOCOL', 'http')
                        store_url = f"{protocol}://{session.store.store_slug}.{domain}/checkout/?payment_id={session.payment_id}"
                        
                        send_mail.mailSender(
                            "store_order_underpaid.html",
                            f"Action Required: Underpaid Order #{invoice.invoice_id}",
                            [invoice.customer_email],
                            {
                                "store_name": session.store.store_name,
                                "customer_name": getattr(invoice, 'customer_name', 'Customer'),
                                "invoice_id": invoice.invoice_id,
                                "amount_expected": str(session.arc_total_amount),
                                "amount_received": str(session.received_amount),
                                "amount_remaining": str(remain),
                                "deposit_address": session.deposit_address,
                                "store_url": store_url
                            }
                        )
                except Exception as exc:
                    logger.warning("Underpaid email failed: %s", exc)

            # Notify checkout via WebSocket
            _notify_checkout(session, tx_hash)

            return transfer

    except Exception as exc:
        logger.exception(
            "Error processing transfer tx=%s log=%s: %s", tx_hash, log_index, exc
        )
        return None


def models_sum(field):
    """Helper import to avoid circular imports."""
    from django.db.models import Sum
    return Sum(field)


def _finalize_invoice(session: ArcPaymentSession):
    """
    Mark the underlying UserInvoices record as completed and credit the merchant.
    Mirrors the Paystack verification flow in data_update.py.
    """
    try:
        from api import models as api_models
        invoice = session.invoice
        if not invoice:
            return

        if invoice.invoice_status == 'completed':
            logger.info("Invoice %s already completed, skipping.", invoice.invoice_id)
            return

        invoice.invoice_status = 'completed'
        invoice.delivery_status = 'processing'
        invoice.save(update_fields=['invoice_status', 'delivery_status'])

        amount_to_credit = float(session.order_amount)
        if invoice.delivery_type == 'system':
            delivery_item = invoice.invoice_items.filter(item_id='DELIVERY_001').first()
            delivery_fee = float(delivery_item.item_amount) if delivery_item else 0.0
            amount_to_credit = max(0.0, amount_to_credit - delivery_fee)

        # Credit merchant wallet
        api_models.UserTransactions.objects.create(
            user=session.merchant,
            trx_status='completed',
            trx_amount=amount_to_credit,
            trx_currency=session.order_currency,
            trx_type='credit',
            description=f"Arc USDC payment for Order #{invoice.invoice_id}",
            trx_source='arc_usdc',
            user_collection_id='0',
            destination_id='0',
        )

        # Notify merchant
        notif_desc = (
            f"Order #{invoice.invoice_id} paid "
            f"{session.received_amount} USDC on Arc. "
            f"Tx: {session.tx_hash}"
        )
        if len(notif_desc) > 100:
            notif_desc = notif_desc[:97] + "..."

        api_models.Notifications.objects.create(
            user=session.merchant,
            title="New Arc USDC Order Paid",
            description=notif_desc,
            notification_type="tranc_success",
            action_url=f"/online-orders/{invoice.invoice_id}",
        )

        # Generate waybill if system delivery
        if invoice.delivery_type == 'system':
            try:
                from api.functions.logistics import process_store_waybill
                process_store_waybill(invoice)
            except Exception as exc:
                logger.warning("Waybill generation failed: %s", exc)

        # Send email to merchant
        try:
            from api.functions import send_mail
            invoice_items_list = list(invoice.invoice_items.all())
            send_mail.mailSender(
                "merchant_new_order.html", 
                f"New Online Order #{invoice.invoice_id}", 
                [session.merchant.user_email], 
                {"invoice": invoice, "invoice_items": invoice_items_list, "amount": float(session.order_amount), "currency": session.order_currency}
            )
        except Exception as exc:
            logger.warning("Merchant email failed: %s", exc)

        # Send order receipt
        try:
            from api.user_data.data_update import send_customer_order_receipt_async
            send_customer_order_receipt_async(invoice.invoice_id)
        except Exception as exc:
            logger.warning("Receipt email failed: %s", exc)

        logger.info(
            "Invoice %s finalized for Arc payment %s",
            invoice.invoice_id, session.payment_id
        )

    except Exception as exc:
        logger.exception("Failed to finalize invoice for session %s: %s", session.payment_id, exc)


def _notify_checkout(session: ArcPaymentSession, tx_hash: str):
    """Push payment status update to the checkout WebSocket."""
    try:
        channel_layer = get_channel_layer()
        group_name = f"arc_payment_{session.payment_id}"
        
        status_to_report = session.status
        if session.is_overpaid:
            status_to_report = 'overpaid'
            
        message = {
            "type": "payment_status_update",
            "payload": {
                "type": "crypto_payment_status",
                "payment_id": session.payment_id,
                "status": status_to_report,
                "amount_received": str(session.received_amount),
                "amount_expected": str(session.arc_total_amount),
                "expires_at": session.expires_at.isoformat(),
                "tx_hash": tx_hash,
                "order_id": session.invoice.invoice_id if session.invoice else None,
                "explorer_url": explorer_tx_url(tx_hash) if tx_hash else None,
            }
        }
        async_to_sync(channel_layer.group_send)(group_name, message)
        logger.info("WebSocket notification sent to group %s", group_name)
    except Exception as exc:
        logger.warning("WebSocket notification failed: %s", exc)


# ── Block cursor helpers ──────────────────────────────────────────────────────

def get_last_processed_block(network: str = ARC_NETWORK) -> int:
    state, created = ArcIndexerState.objects.get_or_create(
        network=network,
        defaults={'last_processed_block': 0}
    )
    if state.last_processed_block == 0:
        try:
            import requests
            from django.conf import settings
            resp = requests.post(settings.ARC_RPC_URL, json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}, timeout=10)
            current_block = int(resp.json().get('result', '0x0'), 16)
            if current_block > 0:
                state.last_processed_block = current_block - 100
                state.save(update_fields=['last_processed_block'])
        except Exception as e:
            logger.warning("Failed to initialize last_processed_block: %s", e)
    return state.last_processed_block


def update_last_processed_block(block: int, network: str = ARC_NETWORK):
    ArcIndexerState.objects.update_or_create(
        network=network,
        defaults={'last_processed_block': block}
    )
