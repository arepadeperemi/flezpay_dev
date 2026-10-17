"""
Arc Payment WebSocket consumer.

Route: ws/store/payment/<payment_id>/

The checkout page connects here to receive real-time payment status updates.
The backend (listener / Celery task) pushes updates via channel_layer.group_send.
"""
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger('arc_payments.consumers')


class ArcPaymentConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for Arc USDC payment status updates.

    The browser connects once the payment popup is open.
    Backend services push status updates via the group channel.
    """

    async def connect(self):
        self.payment_id = self.scope['url_route']['kwargs']['payment_id']
        self.group_name = f"arc_payment_{self.payment_id}"

        # Validate that the payment session exists
        session = await self._get_session(self.payment_id)
        if not session:
            logger.warning(
                "ArcPaymentConsumer: unknown payment_id=%s, rejecting.", self.payment_id
            )
            await self.close(code=4004)
            return

        # Join the payment group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current status immediately on connect
        await self.send(text_data=json.dumps({
            'type': 'crypto_payment_status',
            'payment_id': session.payment_id,
            'status': session.status,
            'amount_expected': str(session.payment_amount),
            'amount_received': str(session.received_amount),
            'expires_at': session.expires_at.isoformat(),
            'tx_hash': session.tx_hash,
        }))

        logger.info(
            "ArcPaymentConsumer connected: payment_id=%s group=%s",
            self.payment_id, self.group_name
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(
            "ArcPaymentConsumer disconnected: payment_id=%s code=%s",
            self.payment_id, close_code
        )

    async def receive(self, text_data):
        """
        Clients may send a 'ping' to keep the connection alive.
        We respond with a 'pong' and current status.
        """
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                session = await self._get_session(self.payment_id)
                if session:
                    await self.send(text_data=json.dumps({
                        'type': 'pong',
                        'payment_id': self.payment_id,
                        'status': session.status,
                    }))
        except Exception:
            pass  # Ignore malformed messages

    # ── Group message handler ─────────────────────────────────────────────────

    async def payment_status_update(self, event):
        """
        Called when the backend pushes a payment_status_update to this group.
        Forward the payload to the connected WebSocket client.
        """
        payload = event.get('payload', {})
        await self.send(text_data=json.dumps(payload))
        logger.info(
            "Pushed status update to checkout WS: payment_id=%s status=%s",
            payload.get('payment_id'), payload.get('status')
        )

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_session(self, payment_id: str):
        from arc_payments.models import ArcPaymentSession
        return ArcPaymentSession.objects.filter(payment_id=payment_id).first()
