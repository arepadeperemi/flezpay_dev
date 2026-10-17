"""
Arc USDC Celery recovery tasks.

scan_arc_usdc_blocks — HTTP RPC recovery scanner.
Reads the block cursor, fetches missed eth_getLogs, processes events.
Scheduled via Celery Beat as a backup to the WebSocket listener.
"""
import logging
from celery import shared_task

logger = logging.getLogger('arc_payments.tasks')


@shared_task(name='arc_payments.tasks.scan_arc_usdc_blocks', bind=True, max_retries=3)
def scan_arc_usdc_blocks(self):
    """
    HTTP RPC recovery scanner.

    1. Read last_processed_block from ArcIndexerState.
    2. Fetch current block number.
    3. Query eth_getLogs filtered to only our active deposit addresses (via topics[2]).
    4. Process each USDC Transfer event.
    5. Advance the cursor.
    """
    import requests
    from arc_payments.config import (
        ARC_RPC_URL, ARC_CHAIN_ID, ARC_NETWORK,
        ARC_USDC_ADDRESS, USDC_TRANSFER_TOPIC,
        ARC_SCANNER_BATCH_SIZE,
    )
    from arc_payments.services import (
        process_transfer_event,
        get_last_processed_block,
        update_last_processed_block,
    )
    from arc_payments.listener import _decode_transfer_log
    from arc_payments.models import ArcPaymentSession

    logger.info("Arc recovery scanner started.")

    try:
        # Get current block
        resp = requests.post(
            ARC_RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
            timeout=15,
        )
        resp.raise_for_status()
        current_block = int(resp.json().get('result', '0x0'), 16)

        last_block = get_last_processed_block(ARC_NETWORK)

        # Fast-forward if too far behind to avoid wasted scanning
        if current_block - last_block > 5000:
            target_block = max(0, current_block - 2000)
            logger.warning(
                "Arc scanner is too far behind (%s blocks). Fast-forwarding to block %s.",
                current_block - last_block, target_block
            )
            last_block = target_block
            update_last_processed_block(last_block, ARC_NETWORK)

        if current_block <= last_block:
            logger.info("Arc scanner: already caught up (block %s).", current_block)
            return

        logger.info(
            "Arc scanner: scanning blocks %s → %s (%s blocks)",
            last_block + 1, current_block, current_block - last_block
        )

        # --- Build targeted deposit address filter ---
        # Only scan for transfers TO our active deposit addresses.
        # Use topics[2] to filter by recipient — this reduces events from thousands
        # of global transfers down to only the ones relevant to our sessions.
        active_sessions = ArcPaymentSession.objects.exclude(
            status__in=[
                ArcPaymentSession.STATUS_PAID,
                ArcPaymentSession.STATUS_CANCELLED,
                ArcPaymentSession.STATUS_FAILED,
                ArcPaymentSession.STATUS_EXPIRED,
            ]
        ).values_list('deposit_address', flat=True)

        # Pad each address into a 32-byte topic (topics[2] = Transfer recipient)
        recipient_topics = [
            '0x000000000000000000000000' + addr[2:]  # strip 0x, pad to 32 bytes
            for addr in active_sessions
            if addr and len(addr) == 42
        ]

        if not recipient_topics:
            logger.info("Arc scanner: no active sessions, skipping scan.")
            update_last_processed_block(current_block, ARC_NETWORK)
            return

        logger.info(
            "Arc scanner: filtering for %d active deposit addresses.",
            len(recipient_topics)
        )

        # Scan in batches — use larger batch size since we filter server-side
        batch_size = max(ARC_SCANNER_BATCH_SIZE, 500)
        from_block = last_block + 1
        total_processed = 0

        while from_block <= current_block:
            to_block = min(from_block + batch_size - 1, current_block)

            log_resp = requests.post(
                ARC_RPC_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_getLogs",
                    "params": [{
                        "fromBlock": hex(from_block),
                        "toBlock": hex(to_block),
                        "address": ARC_USDC_ADDRESS,
                        # topics[0] = Transfer event signature
                        # topics[1] = None (any sender)
                        # topics[2] = list of our deposit addresses (OR filter)
                        "topics": [USDC_TRANSFER_TOPIC, None, recipient_topics],
                    }]
                },
                timeout=30,
            )
            log_resp.raise_for_status()
            result = log_resp.json()

            # Handle RPC error (some nodes return errors for too-large topic arrays)
            if 'error' in result:
                logger.warning(
                    "Arc scanner RPC error (falling back to full scan): %s",
                    result['error']
                )
                # Fallback: full scan without address filter
                log_resp2 = requests.post(
                    ARC_RPC_URL,
                    json={
                        "jsonrpc": "2.0", "id": 3, "method": "eth_getLogs",
                        "params": [{"fromBlock": hex(from_block), "toBlock": hex(to_block),
                                    "address": ARC_USDC_ADDRESS, "topics": [USDC_TRANSFER_TOPIC]}]
                    },
                    timeout=30,
                )
                logs = log_resp2.json().get('result', [])
            else:
                logs = result.get('result', [])

            for log in logs:
                decoded = _decode_transfer_log(log)
                if decoded:
                    process_transfer_event(
                        chain_id=ARC_CHAIN_ID,
                        network=ARC_NETWORK,
                        **decoded,
                    )
                    total_processed += 1

            update_last_processed_block(to_block, ARC_NETWORK)
            from_block = to_block + 1

        logger.info(
            "Arc scanner complete: processed %d events up to block %s",
            total_processed, current_block
        )

    except Exception as exc:
        logger.exception("Arc scanner error: %s", exc)
        raise self.retry(exc=exc, countdown=30)
