"""
Myaza Trust KYC Webhook Handler
Documentation: https://trust.myaza.co/documentation/webhooks
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from api.external.myaza_api import MyazaTrustAPI
from api.models import UserVerificationDetails, UserSecure
from api.tasks import check_user_dual_verification

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def myaza_webhook_view(request):
    """
    Receives real-time verification webhooks from Myaza Trust.
    Headers:
      - X-Myaza-Signature: sha256=<hmac_hex>
      - X-Myaza-Event: e.g. verification.completed, verification.failed, verification.not_found
    """
    signature = request.headers.get('X-Myaza-Signature', '')
    event_type = request.headers.get('X-Myaza-Event', '')

    try:
        raw_body = request.body
        payload = json.loads(raw_body.decode('utf-8'))
    except Exception as e:
        logger.error(f"Failed to decode Myaza webhook body: {e}")
        return JsonResponse({'status': False, 'message': 'Invalid JSON body'}, status=400)

    api_client = MyazaTrustAPI()
    from django.conf import settings

    webhook_secret = getattr(settings, 'MYAZA_WEBHOOK_SECRET', None) or api_client.secret_key

    # Verify signature if secret key is present
    if webhook_secret and signature:
        if not api_client.verify_webhook_signature(raw_body, signature, secret=webhook_secret):
            logger.warning("Invalid Myaza webhook signature")
            return JsonResponse({'status': False, 'message': 'Invalid signature'}, status=401)

    logger.info(f"Received Myaza webhook: {event_type}")

    data = payload.get('data') or payload
    verification_id = data.get('verificationId')
    external_user_id = data.get('externalUserId')
    reason = data.get('reason') or data.get('reasonCode') or ''

    # Lookup verification record
    verification = None
    if verification_id:
        verification = UserVerificationDetails.objects.filter(provider_reference=verification_id).first()

    if not verification and external_user_id:
        user = UserSecure.objects.filter(uniq_id=external_user_id).first()
        if user:
            verification = UserVerificationDetails.objects.filter(user=user, verification_type='KYC').first()

    if not verification:
        logger.info(f"Myaza webhook: No matching verification found for ID {verification_id} or user {external_user_id}")
        return JsonResponse({'status': True, 'message': 'Event received; no matching record'})

    user = verification.user

    v_type = (verification.verification_type or 'KYC').upper()
    from api.functions.verification_emails import send_tier_verification_email
    from api.functions.verification_sync import sync_verified_identity_from_provider

    # Handle event types
    if event_type in ['verification.completed']:
        verification.verification_status = '1'  # Approved
        verification.reason = ''
        verification.save()

        if v_type == 'KYB':
            user.kyb_verified = True
            user.save(update_fields=['kyb_verified'])
        else:
            user.kyc_verified = True
            user.save(update_fields=['kyc_verified'])
            sync_verified_identity_from_provider(verification, payload_data=data, client=api_client)

        check_user_dual_verification(user)
        send_tier_verification_email(user=user, tier_type=v_type, new_status='1')
        logger.info(f"Myaza {v_type} approved for user {user.user_email}")

    elif event_type in ['verification.failed', 'verification.not_found', 'verification.error']:
        verification.verification_status = '2'  # Rejected / Action Required
        if reason:
            verification.reason = f"Provider: {reason}"
        verification.save()

        if v_type == 'KYB':
            user.kyb_verified = False
            user.save(update_fields=['kyb_verified'])
        else:
            user.kyc_verified = False
            user.save(update_fields=['kyc_verified'])

        check_user_dual_verification(user)
        send_tier_verification_email(user=user, tier_type=v_type, new_status='2', reason=reason)
        logger.info(f"Myaza {v_type} {event_type} for user {user.user_email} (Reason: {reason})")

    elif event_type == 'verification.status_updated':
        top_status = data.get('status', '').lower()
        if top_status in ['approved', 'verified']:
            verification.verification_status = '1'
            verification.save()
            if v_type == 'KYB':
                user.kyb_verified = True
                user.save(update_fields=['kyb_verified'])
            else:
                user.kyc_verified = True
                user.save(update_fields=['kyc_verified'])
                sync_verified_identity_from_provider(verification, payload_data=data, client=api_client)
            check_user_dual_verification(user)
            send_tier_verification_email(user=user, tier_type=v_type, new_status='1')
        elif top_status in ['failed', 'declined', 'not_found']:
            verification.verification_status = '2'
            if reason:
                verification.reason = f"Provider: {reason}"
            verification.save()
            if v_type == 'KYB':
                user.kyb_verified = False
                user.save(update_fields=['kyb_verified'])
            else:
                user.kyc_verified = False
                user.save(update_fields=['kyc_verified'])
            check_user_dual_verification(user)
            send_tier_verification_email(user=user, tier_type=v_type, new_status='2', reason=reason)

    return JsonResponse({'status': True, 'message': 'Webhook processed successfully'})
