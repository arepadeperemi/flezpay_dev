import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def format_name_part(name_str):
    """
    Cleans and nicely formats a name string.
    If the name is entirely in UPPERCASE (typical of official government registries),
    it is converted to Title Case (e.g. 'JOHN' -> 'John', 'O'CONNOR' -> 'O'Connor').
    """
    if not name_str or not isinstance(name_str, str):
        return None
    cleaned = name_str.strip()
    if not cleaned:
        return None
    if cleaned.isupper():
        return cleaned.title()
    return cleaned


def extract_identity_from_source(source_dict):
    """
    Extracts first name, last name, DOB, and ID number from diverse
    Myaza response / webhook payload structures.
    """
    if not isinstance(source_dict, dict):
        return {}

    # Gather potential candidate dictionaries in order of specificity
    candidates = []

    # 1. 'result' block (standard Myaza GET /verifications/:id response)
    if isinstance(source_dict.get('result'), dict):
        candidates.append(source_dict['result'])

    # 2. 'identity' block (some webhook schemas and spot checks)
    if isinstance(source_dict.get('identity'), dict):
        candidates.append(source_dict['identity'])

    # 3. Nested within 'data'
    data_block = source_dict.get('data')
    if isinstance(data_block, dict):
        if isinstance(data_block.get('result'), dict):
            candidates.append(data_block['result'])
        if isinstance(data_block.get('identity'), dict):
            candidates.append(data_block['identity'])
        if isinstance(data_block.get('ocrData'), dict):
            candidates.append(data_block['ocrData'])
        if isinstance(data_block.get('extractedData'), dict):
            candidates.append(data_block['extractedData'])
        candidates.append(data_block)

    # 4. Top-level source dict
    candidates.append(source_dict)

    extracted = {
        'first_name': None,
        'last_name': None,
        'middle_name': None,
        'date_of_birth': None,
        'id_number': None,
    }

    # First name keys
    for c in candidates:
        if not extracted['first_name']:
            raw_fn = (
                c.get('firstName') or c.get('first_name') or
                c.get('givenName') or c.get('given_name')
            )
            if raw_fn and isinstance(raw_fn, str):
                extracted['first_name'] = format_name_part(raw_fn)

    # Last name keys
    for c in candidates:
        if not extracted['last_name']:
            raw_ln = (
                c.get('lastName') or c.get('last_name') or
                c.get('familyName') or c.get('family_name') or
                c.get('surname')
            )
            if raw_ln and isinstance(raw_ln, str):
                extracted['last_name'] = format_name_part(raw_ln)

    # Middle name keys
    for c in candidates:
        if not extracted['middle_name']:
            raw_mn = c.get('middleName') or c.get('middle_name')
            if raw_mn and isinstance(raw_mn, str):
                extracted['middle_name'] = format_name_part(raw_mn)

    # Date of birth
    for c in candidates:
        if not extracted['date_of_birth']:
            raw_dob = c.get('dateOfBirth') or c.get('date_of_birth') or c.get('dob')
            if raw_dob:
                if isinstance(raw_dob, str) and raw_dob.strip():
                    try:
                        extracted['date_of_birth'] = datetime.strptime(raw_dob.strip()[:10], '%Y-%m-%d').date()
                    except Exception:
                        pass

    # ID number
    for c in candidates:
        if not extracted['id_number']:
            raw_id = (
                c.get('idNumber') or c.get('id_number') or
                c.get('legalId') or c.get('legal_id')
            )
            if raw_id and isinstance(raw_id, str) and raw_id.strip():
                extracted['id_number'] = raw_id.strip()

    return extracted


def sync_verified_identity_from_provider(verification_record, payload_data=None, client=None):
    """
    Synchronizes verified identity data (first name, last name, date of birth, legal ID)
    from Myaza Trust verification response into UserVerificationDetails and UserDetails.

    - verification_record: instance of UserVerificationDetails
    - payload_data: optional dictionary passed from webhook event or polling response
    - client: optional instance of MyazaTrustAPI

    Returns:
        dict: {
            'success': bool,
            'updated': bool,
            'first_name': str or None,
            'last_name': str or None,
            'error': str or None
        }
    """
    if not verification_record:
        return {'success': False, 'updated': False, 'error': 'No verification record provided'}

    # Only sync for KYC (individual identity) records
    v_type = (verification_record.verification_type or 'KYC').upper()
    if v_type != 'KYC':
        return {'success': True, 'updated': False, 'message': 'Skipped: Not a KYC verification'}

    try:
        from api.models import UserDetails
        from api.external.myaza_api import MyazaTrustAPI

        extracted = extract_identity_from_source(payload_data or {})

        # If names are not in payload_data and we have a provider_reference, fetch full verification report
        if (not extracted.get('first_name') or not extracted.get('last_name')) and verification_record.provider_reference:
            api_client = client or MyazaTrustAPI()
            full_res = api_client.get_full_verification(verification_record.provider_reference)
            if full_res.get('status'):
                fetched_extracted = extract_identity_from_source(full_res.get('data') or full_res)
                for k, v in fetched_extracted.items():
                    if v and not extracted.get(k):
                        extracted[k] = v

        # If names are still missing, fallback to whatever was already saved on verification_record
        first_name = extracted.get('first_name') or format_name_part(verification_record.first_name)
        last_name = extracted.get('last_name') or format_name_part(verification_record.last_name)
        dob = extracted.get('date_of_birth')
        id_number = extracted.get('id_number')

        ver_update_fields = []
        if first_name and verification_record.first_name != first_name:
            verification_record.first_name = first_name
            ver_update_fields.append('first_name')

        if last_name and verification_record.last_name != last_name:
            verification_record.last_name = last_name
            ver_update_fields.append('last_name')

        if dob and verification_record.date_of_birth != dob:
            verification_record.date_of_birth = dob
            ver_update_fields.append('date_of_birth')

        if id_number and not verification_record.legal_id:
            verification_record.legal_id = id_number
            ver_update_fields.append('legal_id')

        if ver_update_fields:
            verification_record.save(update_fields=ver_update_fields)

        # Synchronize to UserDetails
        details_updated = False
        user = verification_record.user
        if user:
            user_details = UserDetails.objects.filter(user=user).first()
            if user_details:
                det_update_fields = []
                if first_name and user_details.first_name != first_name:
                    user_details.first_name = first_name
                    det_update_fields.append('first_name')
                if last_name and user_details.last_name != last_name:
                    user_details.last_name = last_name
                    det_update_fields.append('last_name')

                if det_update_fields:
                    user_details.save(update_fields=det_update_fields)
                    details_updated = True
                    logger.info(
                        f"Updated UserDetails ({user.user_email}) name to '{first_name} {last_name}' "
                        f"from verified identity provider response."
                    )

        updated = bool(ver_update_fields or details_updated)
        return {
            'success': True,
            'updated': updated,
            'first_name': first_name,
            'last_name': last_name,
            'details_updated': details_updated
        }

    except Exception as e:
        logger.error(f"Error syncing verified identity from provider: {e}", exc_info=True)
        return {'success': False, 'updated': False, 'error': str(e)}
