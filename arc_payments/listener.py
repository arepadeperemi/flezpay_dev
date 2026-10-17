"""
Arc USDC WebSocket listener.

This is a LONG-RUNNING process — run it as a separate service:
    python manage.py run_arc_listener

It connects to the dRPC WebSocket, subscribes to USDC Transfer logs,
decodes events, and calls services.process_transfer_event().

Reconnects automatically with exponential backoff.
After reconnect, uses the block cursor to detect missed blocks.
"""
import asyncio
import json
import logging
import os
import time

import websockets

import django

logger = logging.getLogger('arc_payments.listener')


def _decode_transfer_log(log: dict) -> dict | None:
    """
    Decode a raw eth_subscribe log event for a USDC Transfer.

    Log structure (ERC-20 Transfer):
        topics[0] = event signature hash
        topics[1] = from address (padded)
        topics[2] = to address (padded)
        data      = amount (uint256, hex)
    """
    try:
        topics = log.get('topics', [])
        if len(topics) < 3:
            return None

        from_addr = '0x' + topics[1][-40:]   # last 20 bytes
        to_addr = '0x' + topics[2][-40:]
        amount_raw = int(log.get('data', '0x0'), 16)
        tx_hash = log.get('transactionHash', '')
        block_number = int(log.get('blockNumber', '0x0'), 16)
        log_index = int(log.get('logIndex', '0x0'), 16)

        return {
            'from_address': from_addr.lower(),
            'to_address': to_addr.lower(),
            'amount_raw': amount_raw,
            'tx_hash': tx_hash.lower(),
            'block_number': block_number,
            'log_index': log_index,
        }
    except Exception as exc:
        logger.warning("Failed to decode log: %s — %s", log, exc)
        return None


async def listen_forever():
    """
    Main listener loop. Connects to dRPC WS, subscribes to USDC logs,
    processes events, and reconnects on failure.
    """
    from asgiref.sync import sync_to_async
    from arc_payments.config import (
        ARC_WS_URL, ARC_CHAIN_ID, ARC_NETWORK,
        ARC_USDC_ADDRESS, USDC_TRANSFER_TOPIC,
    )
    from arc_payments.services import (
        process_transfer_event, get_last_processed_block,
        update_last_processed_block,
    )

    # Wrap sync DB functions for async context
    _get_last_block = sync_to_async(get_last_processed_block)
    _update_last_block = sync_to_async(update_last_processed_block)
    _process_event = sync_to_async(process_transfer_event)

    backoff = 2  # seconds, doubles on each failure

    while True:
        try:
            logger.info("Arc listener: connecting to %s", ARC_WS_URL[:60] + "...")

            async with websockets.connect(
                ARC_WS_URL,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                backoff = 2  # reset on success

                # 1. Verify chain ID
                await ws.send(json.dumps({
                    "jsonrpc": "2.0", "id": 0,
                    "method": "eth_chainId", "params": []
                }))
                chain_response = json.loads(await ws.recv())
                chain_id_hex = chain_response.get('result', '0x0')
                chain_id = int(chain_id_hex, 16)
                if chain_id != ARC_CHAIN_ID:
                    logger.error(
                        "Chain ID mismatch: expected %s, got %s. Disconnecting.",
                        ARC_CHAIN_ID, chain_id
                    )
                    await asyncio.sleep(30)
                    continue
                logger.info("Arc listener: chain ID verified (%s)", chain_id)

                # 2. Check for missed blocks since last cursor
                last_block = await _get_last_block(ARC_NETWORK)
                if last_block > 0:
                    await _catchup_missed_blocks(ws, last_block, ARC_CHAIN_ID, ARC_NETWORK, _process_event, _update_last_block)

                # 3. Subscribe to USDC Transfer logs
                await ws.send(json.dumps({
                    "jsonrpc": "2.0", "id": 1,
                    "method": "eth_subscribe",
                    "params": [
                        "logs",
                        {
                            "address": ARC_USDC_ADDRESS,
                            "topics": [USDC_TRANSFER_TOPIC]
                        }
                    ]
                }))
                sub_response = json.loads(await ws.recv())
                subscription_id = sub_response.get('result')
                if not subscription_id:
                    logger.error("Subscription failed: %s", sub_response)
                    await asyncio.sleep(backoff)
                    continue
                logger.info(
                    "Arc listener: subscribed to USDC logs (sub_id=%s)", subscription_id
                )

                # 4. Listen forever
                async for raw in ws:
                    try:
                        message = json.loads(raw)
                        params = message.get('params', {})
                        result = params.get('result', {})

                        if not isinstance(result, dict):
                            continue

                        decoded = _decode_transfer_log(result)
                        if not decoded:
                            continue

                        logger.info(
                            "New USDC Transfer: %s → %s  %s raw  (block %s tx %s)",
                            decoded['from_address'][:12],
                            decoded['to_address'][:12],
                            decoded['amount_raw'],
                            decoded['block_number'],
                            decoded['tx_hash'][:14],
                        )

                        # Process synchronously (Django ORM is sync)
                        await _process_event(
                            chain_id=ARC_CHAIN_ID,
                            network=ARC_NETWORK,
                            tx_hash=decoded['tx_hash'],
                            log_index=decoded['log_index'],
                            block_number=decoded['block_number'],
                            from_address=decoded['from_address'],
                            to_address=decoded['to_address'],
                            amount_raw=decoded['amount_raw'],
                        )

                        # Advance block cursor
                        await _update_last_block(
                            decoded['block_number'], ARC_NETWORK
                        )

                    except Exception as exc:
                        logger.exception("Error processing WS message: %s", exc)

        except (websockets.exceptions.ConnectionClosed,
                websockets.exceptions.WebSocketException) as exc:
            logger.warning(
                "Arc WebSocket disconnected: %s — reconnecting in %ss", exc, backoff
            )
        except Exception as exc:
            logger.exception(
                "Arc listener unexpected error — reconnecting in %ss: %s", backoff, exc
            )

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


async def _catchup_missed_blocks(ws, last_block: int, chain_id: int, network: str, _process_event=None, _update_last_block=None):
    """
    Query eth_getLogs for any blocks missed since last_block.
    Called after reconnect to fill the gap.
    """
    try:
        from arc_payments.config import ARC_USDC_ADDRESS, USDC_TRANSFER_TOPIC
        from arc_payments.services import process_transfer_event, update_last_processed_block
        from asgiref.sync import sync_to_async

        if _process_event is None:
            _process_event = sync_to_async(process_transfer_event)
        if _update_last_block is None:
            _update_last_block = sync_to_async(update_last_processed_block)

        # Get current block
        await ws.send(json.dumps({
            "jsonrpc": "2.0", "id": 99,
            "method": "eth_blockNumber", "params": []
        }))
        resp = json.loads(await ws.recv())
        current_block = int(resp.get('result', '0x0'), 16)

        if current_block <= last_block:
            return

        logger.info(
            "Arc listener catch-up: scanning blocks %s → %s",
            last_block + 1, current_block
        )

        from_block_hex = hex(last_block + 1)
        to_block_hex = hex(current_block)

        await ws.send(json.dumps({
            "jsonrpc": "2.0", "id": 98,
            "method": "eth_getLogs",
            "params": [{
                "fromBlock": from_block_hex,
                "toBlock": to_block_hex,
                "address": ARC_USDC_ADDRESS,
                "topics": [USDC_TRANSFER_TOPIC],
            }]
        }))

        logs_resp = json.loads(await ws.recv())
        logs = logs_resp.get('result', [])

        from asgiref.sync import sync_to_async
        for log in logs:
            decoded = _decode_transfer_log(log)
            if decoded:
                await _process_event(
                    chain_id=chain_id,
                    network=network,
                    **decoded,
                )

        await _update_last_block(current_block, network)
        logger.info(
            "Arc listener catch-up complete: processed %d logs up to block %s",
            len(logs), current_block
        )

    except Exception as exc:
        logger.warning("Catch-up failed (non-fatal): %s", exc)
