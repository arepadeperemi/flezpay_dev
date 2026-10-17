"""
Arc USDC Payment API views.

Endpoints (all prefixed with /api/store/checkout/crypto/arc/):
  POST create/             — create or retrieve a payment session
  GET  <payment_id>/       — poll payment status
  GET  /api/arc/health/    — health check
"""
import base64
import io
import logging

import qrcode
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api import models as api_models
from arc_payments.config import (
    ARC_CHAIN_ID,
    ARC_NETWORK,
    ARC_USDC_ADDRESS,
    ARC_USDC_DECIMALS,
    ARC_EXPLORER_URL,
    ARC_ENABLED,
    explorer_tx_url,
)
from arc_payments.models import ArcPaymentSession
from arc_payments.services import create_or_get_payment_session
from arc_payments.wallet import verify_rpc_connection

logger = logging.getLogger('arc_payments.views')


def _qr_base64(data: str) -> str:
    """Generate a QR code PNG and return it as a base64 data URI."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="white", back_color="black")
    buf = io.BytesIO()
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


class ArcPaymentCreateView(APIView):
    """
    POST /api/store/checkout/crypto/arc/create/

    Request body:
        { "invoice_id": "INV-XXXX", "store_slug": "my-store" }

    Response:
        {
          "success": true,
          "payment_id": "PAY-xxx",
          "network": "arc-testnet",
          "chain_id": 5042002,
          "token": "USDC",
          "token_address": "0x360...",
          "amount": "25.000000",
          "deposit_address": "0x...",
          "expires_at": "2026-...",
          "status": "awaiting_payment",
          "qr_code": "data:image/png;base64,...",
          "explorer_url": "https://testnet.arcscan.app"
        }
    """
    authentication_classes = []  # anonymous store checkout
    permission_classes = []

    def post(self, request):
        if not ARC_ENABLED:
            return Response(
                {'success': False, 'message': 'Arc payments not enabled.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        invoice_id = request.data.get('invoice_id')
        store_slug = request.data.get('store_slug')

        if not invoice_id or not store_slug:
            return Response(
                {'success': False, 'message': 'invoice_id and store_slug are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Load the invoice
        invoice = api_models.UserInvoices.objects.filter(
            invoice_id=invoice_id
        ).select_related('user_id').first()
        if not invoice:
            return Response(
                {'success': False, 'message': 'Invoice not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Load the store
        store = api_models.BusinessDetails.objects.filter(
            store_slug=store_slug
        ).first()
        if not store:
            return Response(
                {'success': False, 'message': 'Store not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate invoice belongs to this store's merchant
        if invoice.user_id != store.user:
            return Response(
                {'success': False, 'message': 'Invoice does not belong to this store.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Invoice must still be payable
        if invoice.invoice_status == 'completed':
            return Response(
                {'success': False, 'message': 'Invoice already paid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = create_or_get_payment_session(
                invoice=invoice,
                store=store,
                merchant=store.user,
            )
        except Exception as exc:
            logger.exception("Failed to create Arc payment session: %s", exc)
            return Response(
                {'success': False, 'message': 'Could not create payment session.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Generate QR code containing the deposit address
        qr_data = session.deposit_address
        qr_base64 = _qr_base64(qr_data)

        return Response({
            'success': True,
            'payment_id': session.payment_id,
            'network': session.network,
            'chain_id': session.chain_id,
            'token': session.token,
            'token_address': ARC_USDC_ADDRESS,
            'token_decimals': ARC_USDC_DECIMALS,
            'amount': str(session.arc_total_amount),
            'order_amount': str(session.order_amount),
            'order_currency': session.order_currency,
            'deposit_address': session.deposit_address,
            'expires_at': session.expires_at.isoformat(),
            'status': session.status,
            'qr_code': qr_base64,
            'explorer_url': ARC_EXPLORER_URL,
        })


class ArcPaymentStatusView(APIView):
    """
    GET /api/store/checkout/crypto/arc/<payment_id>/

    Returns current payment status for REST polling fallback.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, payment_id):
        session = ArcPaymentSession.objects.filter(
            payment_id=payment_id
        ).first()
        if not session:
            return Response(
                {'success': False, 'message': 'Payment session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Auto-expire if past expiry time
        if (
            session.status == ArcPaymentSession.STATUS_AWAITING
            and session.is_expired
        ):
            session.status = ArcPaymentSession.STATUS_EXPIRED
            session.save(update_fields=['status'])

        status_to_report = session.status
        if session.is_overpaid:
            status_to_report = 'overpaid'

        # Generate QR code containing the deposit address
        qr_data = session.deposit_address
        qr_base64 = _qr_base64(qr_data)

        data = {
            'success': True,
            'payment_id': session.payment_id,
            'status': status_to_report,
            'amount': str(session.arc_total_amount),
            'amount_expected': str(session.arc_total_amount),
            'amount_received': str(session.received_amount),
            'expires_at': session.expires_at.isoformat(),
            'deposit_address': session.deposit_address,
            'qr_code': qr_base64,
            'tx_hash': session.tx_hash,
            'order_id': session.invoice.invoice_id if session.invoice else None,
        }
        if session.tx_hash:
            data['explorer_url'] = explorer_tx_url(session.tx_hash)

        return Response(data)


class ArcHealthView(APIView):
    """
    GET /api/arc/health/

    Returns health status of Arc RPC connectivity.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from arc_payments.services import get_last_processed_block
        from arc_payments.models import ArcIndexerState

        rpc_status = verify_rpc_connection()
        last_block = get_last_processed_block()

        return Response({
            'arc_rpc': 'healthy' if rpc_status.get('ok') else 'unhealthy',
            'arc_chain_id': rpc_status.get('chain_id'),
            'arc_last_processed_block': last_block,
            'arc_enabled': ARC_ENABLED,
            'rpc_error': rpc_status.get('error'),
        })
