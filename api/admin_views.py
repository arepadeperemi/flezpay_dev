from api.models import Backer
from api.user_data.data_views import calculate_total_balance
from api.external.encryption import Encryption
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import json
import logging
from decimal import Decimal
from .models import UserSecure, UserDetails, CryptoAssets, CryptoAssetChains, UserTransactions, UserVerificationDetails, Notifications, BusinessDetails, UserManagers, UserItems, UserInvoices, UserInvoiceItems, SubscriptionPlans, CashierDepartments, CryptoLedger, CryptoLedgerSweepWallet, JobPosition, JobApplication, TeamMember, SiteSettings, ContactMessage, HelpArticle, BlogPost, BlogCategory, HelpCategory, FailedWaybills
from django.db.models import Sum, Count, Q
from datetime import datetime, timedelta
from django.utils import timezone
from .functions import misc
from django.contrib.auth.hashers import make_password
import hashlib
import traceback
from api.models import SystemErrorLog, FailedWaybills, Ticket, Department, TicketMessage
from django.db import transaction
logger = logging.getLogger(__name__)

def is_admin_user(user):
    """Check if user is an admin (superuser)"""
    if not hasattr(user, 'is_superuser'):
        return False
    return user.is_authenticated and user.is_superuser

# Create a superuser for admin access using UserSecure
def create_admin_user():
    admin_email = 'admin@flezpay.com'
    admin_password = 'admin123'
    
    # Check if admin user exists
    if not UserSecure.objects.filter(user_email=admin_email, is_superuser=True).exists():
        # Hash password twice (as per the app's convention)
        hashed_password = misc.hash_md5(misc.hash_md5(admin_password))
        
        # Generate a unique user_id
        import random
        user_id = str(random.randint(1000000000, 9999999999))
        
        # Ensure unique user_id
        while UserSecure.objects.filter(user_id=user_id).exists():
            user_id = str(random.randint(1000000000, 9999999999))
        
        UserSecure.objects.create(
            user_email=admin_email,
            password=hashed_password,
            user_id=user_id,
            account_type='admin',
            is_superuser=True,
            is_active=True,
            is_verified=True,
            user_phone=0  # Placeholder
        )

def check_admin_auth(request):
    """Check if user is authenticated as admin"""
    return request.session.get('admin_authenticated', False)

def require_admin_auth(func):
    """Decorator to require admin authentication. Works for both DRF api_view and plain Django views."""
    import functools
    from django.http import HttpResponseRedirect
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not check_admin_auth(request):
            # Check if this is a DRF api_view (has request.accepted_renderer set by DRF)
            if hasattr(request, 'accepted_renderer'):
                return Response({
                    'status': False,
                    'message': 'Authentication required. Please login.'
                }, status=status.HTTP_401_UNAUTHORIZED)
            # Plain Django view — redirect to the admin login page
            return HttpResponseRedirect('/admin/login/?next=' + request.path)
        return func(request, *args, **kwargs)
    return wrapper

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_logout(request):
    """Admin logout endpoint"""
    request.session.flush()
    return Response({
        'status': True,
        'message': 'Logged out successfully'
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_login(request):
    """Admin login endpoint"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    # Hash password twice (as per app convention)
    hashed_password = misc.hash_md5(misc.hash_md5(password))
    
    # Try to find admin user by email or user_id
    try:
        user = UserSecure.objects.get(
            Q(user_email=username) | Q(user_id=username),
            password=hashed_password,
            is_superuser=True,
            is_active=True
        )
        
        # Create a session for the user
        # Since UserSecure doesn't work with Django's login(), we'll use session directly
        request.session['admin_user_id'] = user.user_id
        request.session['admin_authenticated'] = True
        
        return Response({
            'status': True,
            'message': 'Login successful',
            'user': {
                'user_id': user.user_id,
                'email': user.user_email
            }
        }, status=status.HTTP_200_OK)
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Invalid credentials or not an admin user'
        }, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET'])
@require_admin_auth
def admin_users(request):
    """Get paginated list of users (excluding admin accounts)"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))
    search = request.GET.get('search', '')
    
    # Exclude admin accounts (is_superuser=True)
    users_query = UserSecure.objects.filter(is_superuser=False).prefetch_related('details', 'verification').order_by('-date_created')
    
    if search:
        users_query = users_query.filter(
            Q(user_email__icontains=search) |
            Q(user_id__icontains=search) |
            Q(user_phone__icontains=search)
        )
    
    paginator = Paginator(users_query, per_page)
    page_obj = paginator.get_page(page)
    
    users_data = []
    for user in page_obj:
        try:
            details = user.details.first()
            
            # Check verification status - if verified and account_type is not 'individual', set to 'business'
            account_type = user.account_type
            verification = user.verification.filter(verification_status='1').first()
            if verification and verification.account_type and verification.account_type.lower() != 'individual':
                account_type = 'business'
            
            users_data.append({
                'id': user.user_id,
                'email': user.user_email or '',
                'phone': str(user.user_phone) if user.user_phone else '',
                'account_type': account_type,
                'is_verified': user.is_verified,
                'is_active': user.is_active,
                'date_created': user.date_created,
                'first_name': details.first_name if details else '',
                'last_name': details.last_name if details else '',
            })
        except:
            # Check verification status even in exception case
            account_type = user.account_type
            try:
                verification = user.verification.filter(verification_status='1').first()
                if verification and verification.account_type and verification.account_type.lower() != 'individual':
                    account_type = 'business'
            except:
                pass
            
            users_data.append({
                'id': user.user_id,
                'email': user.user_email or '',
                'phone': str(user.user_phone) if user.user_phone else '',
                'account_type': account_type,
                'is_verified': user.is_verified,
                'is_active': user.is_active,
                'date_created': user.date_created,
                'first_name': '',
                'last_name': '',
            })
    
    return Response({
        'status': True,
        'data': users_data,
        'pagination': {
            'current_page': page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'per_page': per_page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })

@api_view(['GET'])
@require_admin_auth
def admin_user_detail(request, user_id):
    """Get single user details"""
    try:
        user = UserSecure.objects.prefetch_related('details', 'verification').get(user_id=user_id)
        details = user.details.first()
        
        # Check verification status - if verified and account_type is not 'individual', set to 'business'
        account_type = user.account_type
        verification = user.verification.filter(verification_status='1').first()
        if verification and verification.account_type and verification.account_type.lower() != 'individual':
            account_type = 'business'
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0
        try:
            wallet_balance = float(calculate_total_balance(user))
        except Exception as e:
            print(f"Error calculating balance: {e}")
            pass
            
        # Fetch Business Details (Store)
        business = user.business_details.first()
        store_data = {}
        if business:
            store_data = {
                'store_setup': business.store_setup,
                'store_name': business.store_name or '',
                'store_domain': business.store_domain or '',
                'business_name': business.business_name or '',
            }
            
        # Fetch Invoice Metrics
        invoices = user.invoice.all()
        invoice_data = {
            'total_count': invoices.count(),
            'pending_count': invoices.filter(invoice_status='pending').count(),
            'completed_count': invoices.filter(invoice_status='completed').count(),
        }

        # Fetch Account Status History
        status_history_qs = user.status_history.select_related('admin_user').all()[:20]
        status_history_data = []
        for h in status_history_qs:
            admin_email = h.admin_user.user_email if h.admin_user else 'System'
            status_history_data.append({
                'action': 'Activated' if h.status_is_active else 'Deactivated',
                'reason': h.reason or 'No reason provided',
                'admin_email': admin_email,
                'created_at': h.created_at.isoformat()
            })

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'id': user.user_id,
                'email': user.user_email or '',
                'phone': str(user.user_phone) if user.user_phone else '',
                'account_type': account_type,
                'is_verified': user.is_verified,
                'is_active': user.is_active,
                'date_created': user.date_created,
                'first_name': details.first_name if details else '',
                'last_name': details.last_name if details else '',
                'country': details.user_country if details else '',
                'currency': details.currency if details and hasattr(details, 'currency') else 'NGN',
                'paystack_user_id': user.paystack_user_id or '',
                'transfers_disabled': user.transfers_disabled,
                'withdrawals_disabled': user.withdrawals_disabled,
                'store': store_data,
                'invoices': invoice_data,
                'status_history': status_history_data,
            }
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT', 'DELETE'])
@csrf_exempt
@require_admin_auth
def admin_user_update(request, user_id):
    """Update or delete user"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        
        if request.method == 'PUT':
            is_active = request.data.get('is_active')
            reason = request.data.get('reason', '')
            is_verified = request.data.get('is_verified')
            transfers_disabled = request.data.get('transfers_disabled')
            withdrawals_disabled = request.data.get('withdrawals_disabled')
            
            # Track changes to send emails
            transfers_changed = False
            withdrawals_changed = False
            transfers_was_disabled = user.transfers_disabled
            withdrawals_was_disabled = user.withdrawals_disabled
            is_active_changed = False
            was_active = user.is_active
            
            if is_active is not None:
                if user.is_active != is_active:
                    is_active_changed = True
                user.is_active = is_active
            if is_verified is not None:
                user.is_verified = is_verified
            if transfers_disabled is not None:
                if user.transfers_disabled != transfers_disabled:
                    transfers_changed = True
                user.transfers_disabled = transfers_disabled
            if withdrawals_disabled is not None:
                if user.withdrawals_disabled != withdrawals_disabled:
                    withdrawals_changed = True
                user.withdrawals_disabled = withdrawals_disabled
            
            user.save()
            
            # Send email notification if account status changed
            if is_active_changed:
                try:
                    from api.models import AccountStatusHistory
                    AccountStatusHistory.objects.create(
                        user=user,
                        admin_user=request.user,
                        status_is_active=is_active,
                        reason=reason
                    )
                except Exception as e:
                    print(f"Failed to log account status history: {str(e)}")
                    
                try:
                    from api.tasks import send_account_status_email_task
                    send_account_status_email_task.delay(user.user_id, is_active)
                except Exception as e:
                    print(f"Failed to queue account status email task: {str(e)}")
            
            # Send logout signal via WebSocket if user was deactivated
            if is_active_changed and not is_active:
                try:
                    from api.signals import send_user_logout_signal
                    send_user_logout_signal(user.user_id)
                except Exception as e:
                    pass
            
            # Send email notifications if transfers or withdrawals status changed
            if transfers_changed:
                try:
                    from api.functions import send_mail
                    from api.models import UserDetails
                    from datetime import datetime
                    from django.utils import timezone
                    
                    user_details = UserDetails.objects.filter(user=user).first()
                    first_name = user_details.first_name if user_details and user_details.first_name else "User"
                    current_year = datetime.now().year
                    
                    if transfers_disabled:
                        # Send disabled email
                        send_mail.mailSender(
                            'transfers_disabled.html',
                            'FlezPay Account Security Alert - Transfers Disabled',
                            [user.user_email],
                            {
                                'first_name': first_name,
                                'current_year': current_year
                            }
                        )
                    else:
                        # Send enabled email
                        send_mail.mailSender(
                            'transfers_enabled.html',
                            'FlezPay Account Update - Transfers Enabled',
                            [user.user_email],
                            {
                                'first_name': first_name,
                                'current_year': current_year
                            }
                        )
                except Exception as e:
                    pass
            
            if withdrawals_changed:
                try:
                    from api.functions import send_mail
                    from api.models import UserDetails
                    from datetime import datetime
                    from django.utils import timezone
                    
                    user_details = UserDetails.objects.filter(user=user).first()
                    first_name = user_details.first_name if user_details and user_details.first_name else "User"
                    current_year = datetime.now().year
                    
                    if withdrawals_disabled:
                        # Send disabled email
                        send_mail.mailSender(
                            'withdrawals_disabled.html',
                            'FlezPay Account Security Alert - Withdrawals Disabled',
                            [user.user_email],
                            {
                                'first_name': first_name,
                                'current_year': current_year
                            }
                        )
                    else:
                        # Send enabled email
                        send_mail.mailSender(
                            'withdrawals_enabled.html',
                            'FlezPay Account Update - Withdrawals Enabled',
                            [user.user_email],
                            {
                                'first_name': first_name,
                                'current_year': current_year
                            }
                        )
                except Exception as e:
                    pass

            if withdrawals_changed or transfers_changed:
                try:
                    from api.signals import send_user_data_update
                    send_user_data_update(user.user_id)
                except Exception:
                    pass
            
            return Response({
                'status': True,
                'message': 'User updated successfully'
            })
        
        elif request.method == 'DELETE':
            user.delete()
            return Response({
                'status': True,
                'message': 'User deleted successfully'
            })
            
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_users_delete_batch(request):
    """Delete multiple users"""
    try:
        user_ids = request.data.get('user_ids', [])
        if not user_ids:
            return Response({
                'status': False,
                'message': 'No users selected for deletion'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        UserSecure.objects.filter(user_id__in=user_ids).delete()
        
        return Response({
            'status': True,
            'message': f'{len(user_ids)} users deleted successfully'
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_user_transactions(request, user_id):
    """Get user transactions"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        limit = int(request.GET.get('limit', 10))
        
        transactions = UserTransactions.objects.filter(user=user).order_by('-timestamp')[:limit]
        
        transactions_data = []
        for trx in transactions:
            transactions_data.append({
                'id': str(trx.trx_id),
                'amount': trx.trx_amount,
                'currency': trx.trx_currency,
                'type': trx.trx_type,
                'status': trx.trx_status,
                'description': trx.description or '',
                'timestamp': trx.timestamp.isoformat() if trx.timestamp else None,
            })
        
        return Response({
            'status': True,
            'data': transactions_data
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_user_verification(request, user_id):
    """Get user verification details"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        verification = user.verification.order_by('-timestamp').first()
        
        if not verification:
            return Response({
                'status': True,
                'data': None,
                'message': 'No verification found for this user'
            })
        
        # Build full URLs for media files
        def get_media_url(field):
            if field and hasattr(field, 'url'):
                return request.build_absolute_uri(field.url)
            return None
        
        verification_data = {
            'id': verification.id,
            'verification_type': verification.verification_type or '',
            'verification_id': verification.verification_id or '',
            'account_type': verification.account_type or '',
            'user_address': verification.user_address or '',
            'legal_id': verification.legal_id or '',
            'verification_status': str(verification.verification_status) if verification.verification_status else '0',
            'reason': verification.reason or '',
            'timestamp': verification.timestamp.isoformat() if verification.timestamp else None,
            'proof_of_address': get_media_url(verification.proof_of_address),
            'user_image': get_media_url(verification.user_image),
            'driver_licence': get_media_url(verification.driver_licence),
            'user_video': get_media_url(verification.user_video),
        }
        
        return Response({
            'status': True,
            'data': verification_data
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_crypto_assets(request):
    """Get all crypto assets"""
    assets = CryptoAssets.objects.all().prefetch_related('chains')
    
    assets_data = []
    for asset in assets:
        chains = [{
            'id': chain.uniq_id,
            'chain_id': chain.chain_id,
            'name': chain.name,
            'description': chain.description or '',
            'icon': chain.icon.url if chain.icon else None,
        } for chain in asset.chains.all()]
        
        assets_data.append({
            'id': asset.crypto_uniq_id,
            'asset_id': asset.asset_id,
            'name': asset.name,
            'icon': asset.icon.url if asset.icon else None,
            'chains': chains,
        })
    
    return Response({
        'status': True,
        'data': assets_data
    })

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_add_crypto_asset(request):
    """Add new crypto asset"""
    asset_id = request.data.get('asset_id')
    name = request.data.get('name')
    icon = request.FILES.get('icon')
    
    if not asset_id or not name:
        return Response({
            'status': False,
            'message': 'asset_id and name are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        asset = CryptoAssets.objects.create(
            asset_id=asset_id,
            name=name,
            icon=icon if icon else None
        )
        
        return Response({
            'status': True,
            'message': 'Crypto asset added successfully',
            'data': {
                'id': asset.crypto_uniq_id,
                'asset_id': asset.asset_id,
                'name': asset.name,
            }
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_add_crypto_chain(request):
    """Add network/chain to crypto asset"""
    asset_id = request.data.get('asset_id')
    chain_id = request.data.get('chain_id')
    name = request.data.get('name')
    description = request.data.get('description', '')
    icon = request.FILES.get('icon')
    
    if not asset_id or not chain_id or not name:
        return Response({
            'status': False,
            'message': 'asset_id, chain_id, and name are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        asset = CryptoAssets.objects.get(crypto_uniq_id=asset_id)
        chain = CryptoAssetChains.objects.create(
            asset=asset,
            chain_id=chain_id,
            name=name,
            description=description,
            icon=icon if icon else None
        )
        
        return Response({
            'status': True,
            'message': 'Crypto chain added successfully',
            'data': {
                'id': chain.uniq_id,
                'chain_id': chain.chain_id,
                'name': chain.name,
            }
        })
    except CryptoAssets.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Crypto asset not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@csrf_exempt
@require_admin_auth
def admin_delete_crypto_asset(request, asset_id):
    """Delete crypto asset"""
    try:
        asset = CryptoAssets.objects.get(crypto_uniq_id=asset_id)
        asset.delete()
        return Response({
            'status': True,
            'message': 'Crypto asset deleted successfully'
        })
    except CryptoAssets.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Crypto asset not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@csrf_exempt
@require_admin_auth
def admin_delete_crypto_chain(request, chain_id):
    """Delete crypto chain"""
    try:
        chain = CryptoAssetChains.objects.get(uniq_id=chain_id)
        chain.delete()
        return Response({
            'status': True,
            'message': 'Crypto chain deleted successfully'
        })
    except CryptoAssetChains.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Crypto chain not found'
        }, status=status.HTTP_404_NOT_FOUND)

# Admin User Management
@api_view(['GET'])
@require_admin_auth
def admin_list_admins(request):
    """Get list of all admin users"""
    admins = UserSecure.objects.filter(is_superuser=True).order_by('-date_created')
    
    admins_data = []
    for admin in admins:
        admins_data.append({
            'id': admin.user_id,
            'email': admin.user_email or '',
            'user_id': admin.user_id,
            'is_active': admin.is_active,
            'date_created': admin.date_created,
            'account_type': admin.account_type,
            'permissions': admin.admin_permissions or {},
            'settings': admin.admin_settings or {},
        })
    
    return Response({
        'status': True,
        'data': admins_data
    })

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_create_admin(request):
    """Create a new admin user"""
    email = request.data.get('email')
    password = request.data.get('password')
    user_id = request.data.get('user_id')
    
    if not email or not password:
        return Response({
            'status': False,
            'message': 'Email and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if email already exists
    if UserSecure.objects.filter(user_email=email).exists():
        return Response({
            'status': False,
            'message': 'Email already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate user_id if not provided
    if not user_id:
        import random
        user_id = str(random.randint(1000000000, 9999999999))
        while UserSecure.objects.filter(user_id=user_id).exists():
            user_id = str(random.randint(1000000000, 9999999999))
    
    # Check if user_id already exists
    if UserSecure.objects.filter(user_id=user_id).exists():
        return Response({
            'status': False,
            'message': 'User ID already exists'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Hash password twice (as per app convention)
    hashed_password = misc.hash_md5(misc.hash_md5(password))
    
    # Get permissions from request
    permissions = request.data.get('permissions', {})
    if not isinstance(permissions, dict):
        permissions = {}
    
    try:
        admin = UserSecure.objects.create(
            user_email=email,
            password=hashed_password,
            user_id=user_id,
            account_type='admin',
            is_superuser=True,
            is_active=True,
            is_verified=True,
            user_phone=0,  # Placeholder
            admin_permissions=permissions
        )
        
        return Response({
            'status': True,
            'message': 'Admin user created successfully',
            'data': {
                'id': admin.user_id,
                'email': admin.user_email,
            }
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@csrf_exempt
@require_admin_auth
def admin_update_password(request):
    """Update admin user password"""
    user_id = request.data.get('user_id')
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    if not user_id or not new_password:
        return Response({
            'status': False,
            'message': 'User ID and new password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        admin = UserSecure.objects.get(user_id=user_id, is_superuser=True)
        
        # If current_password is provided, verify it
        if current_password:
            hashed_current = misc.hash_md5(misc.hash_md5(current_password))
            if admin.password != hashed_current:
                return Response({
                    'status': False,
                    'message': 'Current password is incorrect'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        hashed_new = misc.hash_md5(misc.hash_md5(new_password))
        admin.password = hashed_new
        admin.save()
        
        return Response({
            'status': True,
            'message': 'Password updated successfully'
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Admin user not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT'])
@csrf_exempt
@require_admin_auth
def admin_update_admin(request, user_id):
    """Update admin user (email, status, etc.)"""
    try:
        admin = UserSecure.objects.get(user_id=user_id, is_superuser=True)
        
        email = request.data.get('email')
        is_active = request.data.get('is_active')
        permissions = request.data.get('permissions')
        
        if email and email != admin.user_email:
            # Check if new email already exists
            if UserSecure.objects.filter(user_email=email).exclude(user_id=user_id).exists():
                return Response({
                    'status': False,
                    'message': 'Email already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            admin.user_email = email
        
        if is_active is not None:
            admin.is_active = is_active
        
        if permissions is not None:
            if isinstance(permissions, dict):
                admin.admin_permissions = permissions
            else:
                return Response({
                    'status': False,
                    'message': 'Permissions must be a valid JSON object'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        admin.save()
        
        return Response({
            'status': True,
            'message': 'Admin user updated successfully'
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Admin user not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@csrf_exempt
@require_admin_auth
def admin_delete_admin(request, user_id):
    """Delete admin user"""
    try:
        admin = UserSecure.objects.get(user_id=user_id, is_superuser=True)
        
        # Prevent deleting yourself
        current_admin_id = request.session.get('admin_user_id')
        if admin.user_id == current_admin_id:
            return Response({
                'status': False,
                'message': 'You cannot delete your own account'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        admin.delete()
        return Response({
            'status': True,
            'message': 'Admin user deleted successfully'
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Admin user not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@require_admin_auth
def admin_get_current_admin(request):
    """Get current logged-in admin user info"""
    admin_user_id = request.session.get('admin_user_id')
    if not admin_user_id:
        return Response({
            'status': False,
            'message': 'Not authenticated'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        admin = UserSecure.objects.get(user_id=admin_user_id, is_superuser=True)
        # Calculate fiat wallet balance
        wallet_balance = 0.0
        try:
            wallet_balance = float(calculate_total_balance(admin))
        except Exception as e:
            print(f"Error calculating balance: {e}")
            pass

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'id': admin.user_id,
                'email': admin.user_email or '',
                'user_id': admin.user_id,
                'permissions': admin.admin_permissions or {},
                'settings': admin.admin_settings or {},
            }
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Admin user not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@require_admin_auth
def admin_dashboard_stats(request):
    """Get dashboard statistics"""
    # Total deposits (credit transactions that are completed)
    total_deposits = UserTransactions.objects.filter(
        trx_type='credit',
        trx_status='completed'
    ).aggregate(total=Sum('trx_amount'))['total'] or 0.0
    
    # Total withdrawals (withdrawal transactions that are completed)
    total_withdrawals = UserTransactions.objects.filter(
        trx_type='withdrawal',
        trx_status='completed'
    ).aggregate(total=Sum('trx_amount'))['total'] or 0.0
    
    # Total margin (deposits - withdrawals)
    total_margin = total_deposits - total_withdrawals
    
    # Total users (excluding admins)
    total_users = UserSecure.objects.exclude(is_superuser=True).exclude(account_type='admin').exclude(user_type='admin').count()
    
    return Response({
        'status': True,
        'data': {
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(total_withdrawals),
            'total_margin': float(total_margin),
            'total_users': total_users
        }
    })

@api_view(['GET'])
@require_admin_auth
def admin_recent_transactions(request):
    """Get recent transactions"""
    limit = int(request.GET.get('limit', 10))
    
    transactions = UserTransactions.objects.select_related('user').order_by('-timestamp')[:limit]
    
    transactions_data = []
    for trx in transactions:
        transactions_data.append({
            'id': str(trx.trx_id),
            'user_id': trx.user.user_id,
            'user_email': trx.user.user_email or '',
            'amount': trx.trx_amount,
            'currency': trx.trx_currency,
            'type': trx.trx_type,
            'status': trx.trx_status,
            'description': trx.description or '',
            'timestamp': trx.timestamp.isoformat() if trx.timestamp else None,
        })
    
    return Response({
        'status': True,
        'data': transactions_data
    })

@api_view(['GET'])
@require_admin_auth
def admin_transactions(request):
    """Get paginated list of transactions"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    search = request.GET.get('search', '')
    trx_type = request.GET.get('type', '')
    trx_status = request.GET.get('status', '')
    
    transactions_query = UserTransactions.objects.select_related('user').order_by('-timestamp')
    
    if search:
        transactions_query = transactions_query.filter(
            Q(user__user_email__icontains=search) |
            Q(user__user_id__icontains=search) |
            Q(trx_id__icontains=search) |
            Q(description__icontains=search)
        )
    
    if trx_type:
        transactions_query = transactions_query.filter(trx_type=trx_type)
    
    if trx_status:
        transactions_query = transactions_query.filter(trx_status=trx_status)
    
    paginator = Paginator(transactions_query, per_page)
    page_obj = paginator.get_page(page)
    
    transactions_data = []
    for trx in page_obj:
        transactions_data.append({
            'id': str(trx.trx_id),
            'user_id': trx.user.user_id,
            'user_email': trx.user.user_email or '',
            'amount': trx.trx_amount,
            'currency': trx.trx_currency,
            'type': trx.trx_type,
            'status': trx.trx_status,
            'description': trx.description or '',
            'timestamp': trx.timestamp.isoformat() if trx.timestamp else None,
        })
    
    return Response({
        'status': True,
        'data': transactions_data,
        'pagination': {
            'current_page': page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'per_page': per_page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })

@api_view(['GET'])
@require_admin_auth
def admin_verifications(request):
    """Get paginated list of verifications"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    verifications_query = UserVerificationDetails.objects.select_related('user').order_by('-timestamp')
    
    if search:
        verifications_query = verifications_query.filter(
            Q(user__user_email__icontains=search) |
            Q(user__user_id__icontains=search) |
            Q(verification_id__icontains=search)
        )
    
    if status_filter:
        verifications_query = verifications_query.filter(verification_status=status_filter)
    
    paginator = Paginator(verifications_query, per_page)
    page_obj = paginator.get_page(page)
    
    verifications_data = []
    for ver in page_obj:
        # Ensure verification_status is explicitly set - default to '0' (pending) if None or empty
        verification_status = ver.verification_status
        if not verification_status or verification_status == '':
            verification_status = '0'
        
        verifications_data.append({
            'id': ver.id,
            'user_id': ver.user.user_id,
            'user_email': ver.user.user_email or '',
            'verification_type': ver.verification_type or '',
            'verification_id': ver.verification_id or '',
            'account_type': ver.account_type or '',
            'verification_status': verification_status,
            'timestamp': ver.timestamp.isoformat() if ver.timestamp else None,
        })
    
    return Response({
        'status': True,
        'data': verifications_data,
        'pagination': {
            'current_page': page,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'per_page': per_page,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })

@api_view(['GET'])
@require_admin_auth
def admin_notifications(request):
    """Get recent notifications (excluding logins, including verifications)"""
    limit = int(request.GET.get('limit', 50))
    filter_type = request.GET.get('filter', 'all')  # 'all', 'unread', 'read'
    
    # Get notifications excluding auth/login types
    notifications_query = Notifications.objects.select_related('user').exclude(
        notification_type='auth'
    )
    
    # Filter by read status
    if filter_type == 'unread':
        notifications_query = notifications_query.filter(is_read=False)
    elif filter_type == 'read':
        notifications_query = notifications_query.filter(is_read=True)
    
    notifications = notifications_query.order_by('-timestamp')[:limit]
    
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'user_id': notif.user.user_id,
            'title': notif.title or '',
            'description': notif.description or '',
            'type': notif.notification_type or '',
            'is_read': notif.is_read,
            'timestamp': notif.timestamp.isoformat() if notif.timestamp else None,
        })
    
    # Get recent verifications (pending and recent approvals/rejections)
    # Note: Verifications don't have is_read, so we only include them in 'all' and 'unread'
    if filter_type in ['all', 'unread']:
        recent_verifications = UserVerificationDetails.objects.select_related('user').order_by('-timestamp')[:5]
        for ver in recent_verifications:
            status_text = 'Pending' if ver.verification_status == '0' else ('Approved' if ver.verification_status == '1' else 'Rejected')
            notifications_data.append({
                'id': f'verification_{ver.id}',
                'user_id': ver.user.user_id,
                'title': 'Verification Update',
                'description': f'User {ver.user.user_id} verification status: {status_text}',
                'type': 'verification',
                'is_read': False,  # Verifications are always considered unread
                'timestamp': ver.timestamp.isoformat() if ver.timestamp else None,
            })
    
    # Sort by timestamp and limit
    notifications_data.sort(key=lambda x: x['timestamp'] or '', reverse=True)
    notifications_data = notifications_data[:limit]
    
    # Get unread count
    unread_count = Notifications.objects.exclude(notification_type='auth').filter(is_read=False).count()
    
    return Response({
        'status': True,
        'data': notifications_data,
        'unread_count': unread_count
    })

@api_view(['GET'])
@require_admin_auth
def admin_analytics_data(request):
    """Get analytics data for charts"""
    # Date range (last 30 days by default)
    days = int(request.GET.get('days', 30))
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())
    
    # Users analytics - registration over time (using date_created as timestamp)
    users_by_day = {}
    users = UserSecure.objects.filter(
        is_superuser=False,
        date_created__gte=start_timestamp,
        date_created__lte=end_timestamp
    )
    
    for user in users:
        day = datetime.fromtimestamp(user.date_created).strftime('%Y-%m-%d')
        users_by_day[day] = users_by_day.get(day, 0) + 1
    
    users_chart_data = {
        'labels': sorted(users_by_day.keys()),
        'data': [users_by_day[label] for label in sorted(users_by_day.keys())]
    }
    
    # Transactions analytics - by type and status
    transactions_by_type = UserTransactions.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date
    ).values('trx_type').annotate(count=Count('trx_id'))
    
    transactions_by_status = UserTransactions.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date
    ).values('trx_status').annotate(count=Count('trx_id'))
    
    # Transactions over time - sum amounts instead of counts
    transactions_by_day = {}
    transactions = UserTransactions.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date,
        trx_status='completed'  # Only count completed transactions for amounts
    )
    
    for trx in transactions:
        day = trx.timestamp.strftime('%Y-%m-%d') if trx.timestamp else ''
        if day:
            transactions_by_day[day] = transactions_by_day.get(day, 0.0) + float(trx.trx_amount or 0)
    
    transactions_chart_data = {
        'labels': sorted(transactions_by_day.keys()),
        'data': [transactions_by_day[label] for label in sorted(transactions_by_day.keys())]
    }
    
    # User activity - transactions per user
    active_users = UserTransactions.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date
    ).values('user__user_id', 'user__user_email').annotate(
        transaction_count=Count('trx_id'),
        total_amount=Sum('trx_amount')
    ).order_by('-transaction_count')[:10]
    
    # Account type distribution
    account_types = UserSecure.objects.filter(
        is_superuser=False
    ).values('account_type').annotate(count=Count('uniq_id'))
    
    # Verification status distribution
    verification_statuses = UserVerificationDetails.objects.values(
        'verification_status'
    ).annotate(count=Count('id'))
    
    # Transaction volume by type
    transaction_volume = UserTransactions.objects.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date,
        trx_status='completed'
    ).values('trx_type').annotate(
        total_amount=Sum('trx_amount'),
        count=Count('trx_id')
    )
    
    return Response({
        'status': True,
        'data': {
            'users': {
                'by_day': users_chart_data,
                'total': UserSecure.objects.filter(is_superuser=False).count(),
                'active': UserSecure.objects.filter(is_superuser=False, is_active=True).count(),
                'verified': UserSecure.objects.filter(is_superuser=False, is_verified=True).count(),
            },
            'transactions': {
                'by_day': transactions_chart_data,
                'by_type': list(transactions_by_type),
                'by_status': list(transactions_by_status),
                'volume_by_type': list(transaction_volume),
                'total': UserTransactions.objects.count(),
                'total_amount': float(UserTransactions.objects.filter(
                    trx_status='completed'
                ).aggregate(total=Sum('trx_amount'))['total'] or 0.0),
            },
            'user_activity': {
                'most_active': list(active_users),
            },
            'account_types': list(account_types),
            'verification_statuses': list(verification_statuses),
        }
    })

@api_view(['GET'])
@require_admin_auth
def admin_verification_detail(request, verification_id):
    """Get verification details by ID"""
    try:
        verification = UserVerificationDetails.objects.select_related('user').get(id=verification_id)
        
        # Build full URLs for media files
        def get_media_url(field):
            if field and hasattr(field, 'url'):
                return request.build_absolute_uri(field.url)
            return None
        
        verification_data = {
            'id': verification.id,
            'user_id': verification.user.user_id,
            'user_email': verification.user.user_email or '',
            'verification_type': verification.verification_type or '',
            'verification_id': verification.verification_id or '',
            'account_type': verification.account_type or '',
            'user_address': verification.user_address or '',
            'legal_id': verification.legal_id or '',
            'verification_status': str(verification.verification_status) if verification.verification_status else '0',
            'reason': verification.reason or '',
            'timestamp': verification.timestamp.isoformat() if verification.timestamp else None,
            'proof_of_address': get_media_url(verification.proof_of_address),
            'user_image': get_media_url(verification.user_image),
            'driver_licence': get_media_url(verification.driver_licence),
            'user_video': get_media_url(verification.user_video),
        }
        
        return Response({
            'status': True,
            'data': verification_data
        })
    except UserVerificationDetails.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Verification not found'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT'])
@csrf_exempt
@require_admin_auth
def admin_verification_update(request, verification_id):
    """Update verification status"""
    try:
        verification = UserVerificationDetails.objects.get(id=verification_id)
        new_status = request.data.get('verification_status')
        
        if new_status is not None:
            # Ensure status is a string
            new_status = str(new_status)
            verification.verification_status = new_status
            
            # Save optional reason if provided
            reason = request.data.get('reason', '')
            if reason:
                verification.reason = reason
            
            verification.save()
            
            # Update user's kyc_verified / kyb_verified and trigger dual verification check
            user = verification.user
            v_type = (verification.verification_type or '').upper()
            if v_type == 'KYC':
                user.kyc_verified = (new_status == '1')
                user.save(update_fields=['kyc_verified'])
                if new_status == '1':
                    try:
                        from api.functions.verification_sync import sync_verified_identity_from_provider
                        sync_verified_identity_from_provider(verification)
                    except Exception as sync_err:
                        pass
            elif v_type == 'KYB':
                user.kyb_verified = (new_status == '1')
                user.save(update_fields=['kyb_verified'])

            # Actively check if both KYC and KYB are verified before marking is_verified=True
            from api.tasks import check_user_dual_verification
            check_user_dual_verification(user)

            # Send individual Tier verification status email
            try:
                from api.functions.verification_emails import send_tier_verification_email
                send_tier_verification_email(user=user, tier_type=v_type, new_status=new_status, reason=reason)
            except Exception as mail_err:
                pass
            
            return Response({
                'status': True,
                'message': 'Verification status updated successfully'
            })
        else:
            return Response({
                'status': False,
                'message': 'verification_status is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except UserVerificationDetails.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Verification not found'
            }, status=status.HTTP_404_NOT_FOUND)

@api_view(['PUT'])
@csrf_exempt
@require_admin_auth
def admin_notifications_mark_read(request):
    """Mark one or all notifications as read"""
    notification_id = request.data.get('notification_id')
    
    if notification_id:
        # Mark specific notification as read
        try:
            notification = Notifications.objects.get(id=notification_id)
            notification.is_read = True
            notification.save()
            return Response({
                'status': True,
                'message': 'Notification marked as read'
            })
        except Notifications.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
    else:
        # Mark all notifications as read
        Notifications.objects.exclude(notification_type='auth').update(is_read=True)
        return Response({
            'status': True,
            'message': 'All notifications marked as read'
        })

@api_view(['GET'])
@require_admin_auth
def admin_pending_verifications_count(request):
    """Get count of pending verifications for menu badge"""
    count = UserVerificationDetails.objects.filter(verification_status='0').count()
    return Response({
        'status': True,
        'count': count
    })

# Template views
@ensure_csrf_cookie
def admin_login_page(request):
    """Render admin login page"""
    create_admin_user()  # Ensure admin user exists
    return render(request, 'admin/login.html')

@ensure_csrf_cookie
def admin_dashboard(request):
    """Render admin dashboard home"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/dashboard_home.html')

@ensure_csrf_cookie
def admin_users_page(request):
    """Render admin users page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/users.html')

@ensure_csrf_cookie
def admin_verifications_page(request):
    """Render admin verifications page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/verifications.html')

@ensure_csrf_cookie
def admin_transactions_page(request):
    """Render admin transactions page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/transactions.html')

@ensure_csrf_cookie
def admin_analytics_page(request):
    """Render admin analytics page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/analytics.html')

@ensure_csrf_cookie
def admin_mail_page(request):
    """Render admin mail page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/mail.html')

@ensure_csrf_cookie
def admin_push_notifications_page(request):
    """Render admin push notifications page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/push_notifications.html')

@ensure_csrf_cookie
def admin_crypto_wallets_page(request):
    """Render admin crypto wallets page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/crypto_wallets.html')

@api_view(['GET', 'PUT'])
@csrf_exempt
@require_admin_auth
def admin_settings_api(request):
    """Get or update admin settings (language, email notifications, currency)"""
    admin_user_id = request.session.get('admin_user_id')
    
    if not admin_user_id:
        return Response({
            'status': False,
            'message': 'Not authenticated'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        admin = UserSecure.objects.get(user_id=admin_user_id, is_superuser=True)
        
        if request.method == 'GET':
            settings = admin.admin_settings or {}
            return Response({
                'status': True,
                'data': {
                    'language': settings.get('language', 'en'),
                    'email_notifications': settings.get('email_notifications', True),
                    'currency': settings.get('currency', 'NGN'),
                    'crypto_sweep_fee_usd': settings.get('crypto_sweep_fee_usd', 1.0),
                    'system_delivery_markup_ngn': settings.get('system_delivery_markup_ngn', 200),
                }
            })
        
        elif request.method == 'PUT':
            language = request.data.get('language')
            email_notifications = request.data.get('email_notifications')
            currency = request.data.get('currency')
            crypto_sweep_fee_usd = request.data.get('crypto_sweep_fee_usd')
            system_delivery_markup_ngn = request.data.get('system_delivery_markup_ngn')
            
            if not admin.admin_settings:
                admin.admin_settings = {}
            
            if language is not None:
                if language not in ['en', 'fr', 'es', 'de', 'it', 'pt']:
                    return Response({
                        'status': False,
                        'message': 'Invalid language code'
                    }, status=status.HTTP_400_BAD_REQUEST)
                admin.admin_settings['language'] = language
            
            if email_notifications is not None:
                admin.admin_settings['email_notifications'] = bool(email_notifications)
            
            if currency is not None:
                if currency not in ['NGN', 'USD', 'EUR']:
                    return Response({
                        'status': False,
                        'message': 'Invalid currency. Must be NGN, USD, or EUR'
                    }, status=status.HTTP_400_BAD_REQUEST)
                admin.admin_settings['currency'] = currency
            
            if crypto_sweep_fee_usd is not None:
                try:
                    fee_value = float(crypto_sweep_fee_usd)
                    if fee_value < 0:
                        return Response({
                            'status': False,
                            'message': 'Crypto sweep fee must be 0 or greater'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    admin.admin_settings['crypto_sweep_fee_usd'] = fee_value
                except (ValueError, TypeError):
                    return Response({
                        'status': False,
                        'message': 'Invalid crypto sweep fee'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            if system_delivery_markup_ngn is not None:
                try:
                    markup_value = float(system_delivery_markup_ngn)
                    if markup_value < 0:
                        return Response({
                            'status': False,
                            'message': 'System delivery markup must be 0 or greater'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    admin.admin_settings['system_delivery_markup_ngn'] = markup_value
                except (ValueError, TypeError):
                    return Response({
                        'status': False,
                        'message': 'Invalid system delivery markup'
                    }, status=status.HTTP_400_BAD_REQUEST)

            admin.save()
            
            return Response({
                'status': True,
                'message': 'Settings updated successfully',
                'data': {
                    'language': admin.admin_settings.get('language', 'en'),
                    'email_notifications': admin.admin_settings.get('email_notifications', True),
                    'currency': admin.admin_settings.get('currency', 'NGN'),
                    'crypto_sweep_fee_usd': admin.admin_settings.get('crypto_sweep_fee_usd', 1.0),
                }
            })
            
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Admin user not found'
        }, status=status.HTTP_404_NOT_FOUND)

@ensure_csrf_cookie
def admin_settings(request):
    """Render admin settings page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/settings.html')

@ensure_csrf_cookie
def admin_user_detail_page(request, user_id):
    """Render user detail page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/user_detail.html', {'user_id': user_id})

@ensure_csrf_cookie
def admin_business_details_page(request, user_id):
    """Render business details page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/business_details.html', {'user_id': user_id})

@api_view(['GET'])
@require_admin_auth
def admin_business_data(request, user_id):
    """Get comprehensive business data"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        
        # Get business details using the foreign key relationship
        # BusinessDetails has ForeignKey to UserSecure with related_name='business_details'
        try:
            business = BusinessDetails.objects.filter(user=user).first()
        except Exception as e:
            business = None
        
        business_data = None
        if business:
            # Get subscription expiry as string (property returns string from get_subscription_expiry)
            subscription_expiry_str = None
            try:
                expiry = business.subscription_expiry
                if expiry:
                    subscription_expiry_str = str(expiry) if expiry else None
            except Exception as e:
                subscription_expiry_str = None
            
            # Handle business_image safely
            business_image_url = None
            try:
                if business.business_image and hasattr(business.business_image, 'url'):
                    business_image_url = request.build_absolute_uri(business.business_image.url)
            except Exception as e:
                business_image_url = None
            
            business_data = {
                'business_name': business.business_name or '',
                'business_image': business_image_url,
                'enable_ai_calls': business.enable_ai_calls,
                'subscription_expiry': subscription_expiry_str,
                'plan_code': business.plan_code,
                'enable_loyalty': business.enable_loyalty,
                'vat_percentage': float(business.vat_percentage) if business.vat_percentage is not None else 0,
                'loyalty_point_equivalent': int(business.loyalty_point_equivalent) if business.loyalty_point_equivalent is not None else 0
            }
            
            # Get subscription plan details
            try:
                if business.plan_code:
                    plan = SubscriptionPlans.objects.get(uniq_id=business.plan_code)
                    business_data['subscription_plan'] = {
                        'plan_name': plan.plan_name,
                        'inventory': plan.inventory,
                        'collection_accounts': plan.collection_accounts,
                        'ai_manager': plan.ai_manager,
                        'ai_calls': plan.ai_calls,
                        'cashiers': plan.cashiers,
                        'payroll': plan.payroll,
                        'support': plan.support,
                        'description': plan.description
                    }
                else:
                    business_data['subscription_plan'] = None
            except SubscriptionPlans.DoesNotExist:
                business_data['subscription_plan'] = None
            except Exception as e:
                business_data['subscription_plan'] = None
        
        return Response({
            'status': True,
            'data': business_data
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return Response({
            'status': False,
            'message': f'Error: {str(e)}',
            'trace': error_trace
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_business_managers(request, user_id):
    """Get paginated managers"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        search = request.GET.get('search', '')
        
        managers = UserManagers.objects.filter(user=user)
        
        if search:
            managers = managers.filter(
                Q(manager_name__icontains=search) |
                Q(manager_email__icontains=search) |
                Q(manager_department__icontains=search)
            )
        
        paginator = Paginator(managers, per_page)
        page_obj = paginator.get_page(page)
        
        managers_data = []
        for manager in page_obj:
            managers_data.append({
                'id': manager.uniq_id,
                'manager_name': manager.manager_name,
                'manager_email': manager.manager_email,
                'manager_department': manager.manager_department,
                'password_changed': manager.password_changed,
                'add_product': manager.add_product,
                'edit_product': manager.edit_product,
                'image': request.build_absolute_uri(manager.image.url) if manager.image else None
            })
        
        return Response({
            'status': True,
            'data': managers_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_business_stocks(request, user_id):
    """Get paginated stocks (items)"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        search = request.GET.get('search', '')
        
        stocks = UserItems.objects.filter(user=user)
        
        if search:
            stocks = stocks.filter(
                Q(item_name__icontains=search) |
                Q(item_description__icontains=search) |
                Q(item_serial_number__icontains=search) |
                Q(item_department__icontains=search)
            )
        
        paginator = Paginator(stocks, per_page)
        page_obj = paginator.get_page(page)
        
        stocks_data = []
        for stock in page_obj:
            stocks_data.append({
                'id': str(stock.item_id),
                'item_name': stock.item_name,
                'item_amount': float(stock.item_amount) if stock.item_amount else 0,
                'item_buy_amount': float(stock.item_buy_amount) if stock.item_buy_amount else 0,
                'item_quantity': stock.item_quantity,
                'item_description': stock.item_description,
                'item_serial_number': stock.item_serial_number,
                'item_expiry': stock.item_expiry,
                'item_department': stock.item_department,
                'is_promo': stock.is_promo,
                'last_adjusted_amount': float(stock.last_adjusted_amount) if stock.last_adjusted_amount else None,
                'last_adjusted_date': stock.last_adjusted_date.isoformat() if stock.last_adjusted_date else None,
                'timestamp': stock.timestamp.isoformat() if stock.timestamp else None
            })
        
        return Response({
            'status': True,
            'data': stocks_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_business_sales(request, user_id):
    """Get paginated sales (invoices)"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        
        sales = UserInvoices.objects.filter(user_id=user)
        
        if search:
            sales = sales.filter(
                Q(uniq_id__icontains=search) |
                Q(trx_id__icontains=search)
            )
        
        if status_filter:
            sales = sales.filter(invoice_status=status_filter)
        
        sales = sales.order_by('-timestamp')
        paginator = Paginator(sales, per_page)
        page_obj = paginator.get_page(page)
        
        sales_data = []
        for sale in page_obj:
            # Calculate total amount from invoice items
            items = sale.invoice_items.all()
            total_amount = sum(float(item.item_amount * item.item_quantity) for item in items)
            
            sales_data.append({
                'id': sale.invoice_id,
                'invoice_status': sale.invoice_status,
                'invoice_type': sale.invoice_type,
                'invoice_payment_type': sale.invoice_payment_type,
                'invoice_note': sale.invoice_note,
                'cashier_id': sale.cashier_id,
                'total_amount': total_amount,
                'items_count': items.count(),
                'timestamp': sale.timestamp.isoformat() if sale.timestamp else None
            })
        
        return Response({
            'status': True,
            'data': sales_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_business_sales_by_cashier(request, user_id):
    """Get sales grouped by cashier"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        
        # Get all invoices with cashier_id
        invoices = UserInvoices.objects.filter(user_id=user).exclude(cashier_id__isnull=True).exclude(cashier_id='')
        
        # Group by cashier and calculate totals
        cashier_sales = {}
        for invoice in invoices:
            cashier_id = invoice.cashier_id
            if cashier_id not in cashier_sales:
                cashier_sales[cashier_id] = {
                    'cashier_id': cashier_id,
                    'total_sales': 0,
                    'total_invoices': 0,
                    'completed_invoices': 0,
                    'pending_invoices': 0
                }
            
            items = invoice.invoice_items.all()
            total_amount = sum(float(item.item_amount * item.item_quantity) for item in items)
            
            cashier_sales[cashier_id]['total_sales'] += total_amount
            cashier_sales[cashier_id]['total_invoices'] += 1
            
            if invoice.invoice_status == 'completed':
                cashier_sales[cashier_id]['completed_invoices'] += 1
            else:
                cashier_sales[cashier_id]['pending_invoices'] += 1
        
        sales_data = []
        for cashier_id, data in cashier_sales.items():
            data['cashier_name'] = f'Cashier {cashier_id}'
            sales_data.append(data)
        
        # Sort by total sales descending
        sales_data.sort(key=lambda x: x['total_sales'], reverse=True)
        
        return Response({
            'status': True,
            'data': sales_data
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_business_ai_usage(request, user_id):
    """Get AI usage statistics"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        business = user.business_details.first()
        
        if not business:
            return Response({
                'status': True,
                'data': {
                    'ai_enabled': False,
                    'ai_usage_percentage': 0,
                    'total_ai_calls': 0,
                    'ai_calls_this_month': 0
                }
            })
        
        # Calculate AI usage percentage
        # This is a placeholder - you'll need to implement actual AI call tracking
        # For now, we'll use a simple calculation based on subscription plan
        ai_usage_percentage = 0
        total_ai_calls = 0
        ai_calls_this_month = 0
        
        if business.enable_ai_calls:
            # Placeholder: You should track actual AI calls in a separate model
            # For now, we'll return a mock percentage
            ai_usage_percentage = 45  # Example: 45% usage
            total_ai_calls = 1250  # Example total
            ai_calls_this_month = 320  # Example this month
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0
        try:
            wallet_balance = float(calculate_total_balance(user))
        except Exception as e:
            print(f"Error calculating balance: {e}")
            pass

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'ai_enabled': business.enable_ai_calls,
                'ai_usage_percentage': ai_usage_percentage,
                'total_ai_calls': total_ai_calls,
                'ai_calls_this_month': ai_calls_this_month
            }
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Mail and Push Notifications endpoints
@api_view(['GET'])
@require_admin_auth
def admin_users_search(request):
    """Search users by name or email"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return Response({
            'status': True,
            'users': []
        })
    
    try:
        from api.models import UserDetails
        
        # Get user uniq_ids from UserDetails that match the query
        matching_user_uniq_ids = set()
        try:
            matching_details = UserDetails.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            ).select_related('user').filter(
                user__is_superuser=False,
                user__is_active=True
            )
            for details in matching_details:
                if details.user:
                    matching_user_uniq_ids.add(details.user.uniq_id)
        except Exception as e:
            pass
        
        # Search UserSecure for matching emails/user_ids
        try:
            users_by_email_ids = set(UserSecure.objects.filter(
                is_superuser=False,
                is_active=True,
                user_email__icontains=query
            ).values_list('uniq_id', flat=True))
            matching_user_uniq_ids.update(users_by_email_ids)
        except Exception as e:
            pass
        
        try:
            users_by_id_ids = set(UserSecure.objects.filter(
                is_superuser=False,
                is_active=True,
                user_id__icontains=query
            ).values_list('uniq_id', flat=True))
            matching_user_uniq_ids.update(users_by_id_ids)
        except Exception as e:
            pass
        
        # Get all unique users (limit to 20)
        user_uniq_ids_list = list(matching_user_uniq_ids)[:20]
        
        if not user_uniq_ids_list:
            return Response({
                'status': True,
                'users': []
            })
        
        users_query = UserSecure.objects.filter(
            uniq_id__in=user_uniq_ids_list
        ).prefetch_related('details')
        
        users_data = []
        for user in users_query:
            try:
                # Get the first UserDetails record for this user
                details = user.details.first()
                
                first_name = ''
                last_name = ''
                full_name = user.user_id
                
                if details:
                    first_name = details.first_name or ''
                    last_name = details.last_name or ''
                    name_parts = [first_name, last_name]
                    full_name = ' '.join([n for n in name_parts if n]).strip()
                    if not full_name:
                        full_name = user.user_id
                
                users_data.append({
                    'user_id': user.user_id,
                    'email': user.user_email or '',
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': full_name
                })
            except Exception as e:
                # If there's an error getting details, still include the user
                pass
                users_data.append({
                    'user_id': user.user_id,
                    'email': user.user_email or '',
                    'first_name': '',
                    'last_name': '',
                    'full_name': user.user_id
                })
        
        return Response({
            'status': True,
            'users': users_data
        })
    except Exception as e:
        error_trace = traceback.format_exc()
        error_trace = traceback.format_exc()
        # print(f"Error in admin_users_search: {str(e)}")
        # print(f"Traceback: {error_trace}")
        return Response({
            'status': False,
            'message': f'Error searching users: {str(e)}',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_mail_preview(request):
    """Preview email with template wrapper"""
    try:
        from django.template.loader import render_to_string
        from datetime import datetime
        
        subject = request.data.get('subject', '')
        content = request.data.get('content', '')
        
        html = render_to_string('emails/admin_mail_template.html', {
            'subject': subject,
            'content': content,
            'current_year': datetime.now().year
        })
        
        return Response({
            'status': True,
            'html': html
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_mail_send(request):
    """Send email to users"""
    try:
        from api.functions import send_mail
        from django.template.loader import render_to_string
        from datetime import datetime
        
        subject = request.data.get('subject', '')
        content = request.data.get('content', '')
        recipient_type = request.data.get('recipient_type', 'all')
        user_ids = request.data.get('user_ids', [])
        
        if not subject or not content:
            return Response({
                'status': False,
                'message': 'Subject and content are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get recipients
        if recipient_type == 'all':
            recipients = UserSecure.objects.filter(
                is_superuser=False,
                is_active=True,
                is_verified=True
            ).exclude(user_email__isnull=True).exclude(user_email='')
        else:
            if not user_ids:
                return Response({
                    'status': False,
                    'message': 'Please select at least one user'
                }, status=status.HTTP_400_BAD_REQUEST)
            recipients = UserSecure.objects.filter(
                user_id__in=user_ids,
                is_superuser=False,
                is_active=True
            ).exclude(user_email__isnull=True).exclude(user_email='')
        
        # Send emails
        sent_count = 0
        failed_count = 0
        
        for user in recipients:
            try:
                user_details = user.details.first()
                first_name = user_details.first_name if user_details and user_details.first_name else "User"
                
                # Send email using the template
                send_mail.mailSender(
                    'admin_mail_template.html',
                    subject,
                    [user.user_email],
                    {
                        'subject': subject,
                        'content': content,
                        'current_year': datetime.now().year,
                        'first_name': first_name
                    }
                )
                sent_count += 1
            except Exception as e:
                print(f"Failed to send email to {user.user_email}: {str(e)}")
                failed_count += 1
        
        return Response({
            'status': True,
            'message': f'Emails sent successfully. Sent: {sent_count}, Failed: {failed_count}',
            'sent_count': sent_count,
            'failed_count': failed_count
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_push_notifications_send(request):
    """Send push notifications to users via FCM"""
    try:
        title = request.data.get('title', '')
        body = request.data.get('body', '')
        action_url = request.data.get('action_url')
        recipient_type = request.data.get('recipient_type', 'all')
        user_ids = request.data.get('user_ids', [])
        
        if not title or not body:
            return Response({
                'status': False,
                'message': 'Title and body are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get recipients
        if recipient_type == 'all':
            recipients = UserSecure.objects.filter(
                is_superuser=False,
                is_active=True
            )
        else:
            if not user_ids:
                return Response({
                    'status': False,
                    'message': 'Please select at least one user'
                }, status=status.HTTP_400_BAD_REQUEST)
            recipients = UserSecure.objects.filter(
                user_id__in=user_ids,
                is_superuser=False,
                is_active=True
            )
        
        # Import FCM service
        from api.functions.fcm_service import send_fcm_to_user
        
        # Prepare notification data
        notification_data = {
            'type': 'admin_notification',
            'action_url': action_url or ''
        }
        
        # Send FCM notifications and create in-app notifications
        sent_count = 0
        fcm_success_count = 0
        fcm_failure_count = 0
        errors = []
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Starting to send push notifications to {recipients.count()} users")
        
        for user in recipients:
            try:
                logger.info(f"Processing user {user.user_id} ({user.user_email})")
                
                # Create in-app notification
                # Note: Notifications model uses 'title' and 'description', not 'notification_title' and 'notification_message'
                # Also, notification_type must be one of: 'auth', 'basic', 'tranc_success', 'tranc_error'
                # Using 'basic' as the type for admin notifications
                # Description field has max_length=100, so truncate if necessary
                description = body[:100] if len(body) > 100 else body
                notification_title = title[:100] if len(title) > 100 else title
                
                Notifications.objects.create(
                    user=user,
                    title=notification_title,
                    description=description,
                    notification_type='basic'  # Changed from 'admin' to 'basic' as 'admin' is not in choices
                )
                logger.info(f"In-app notification created for user {user.user_id}")
                
                # Send FCM notification
                fcm_result = send_fcm_to_user(
                    user_id=user.user_id,
                    title=title,
                    body=body,
                    data=notification_data
                )
                
                logger.info(f"FCM result for user {user.user_id}: {fcm_result}")
                
                if fcm_result.get('success_count', 0) > 0:
                    fcm_success_count += fcm_result.get('success_count', 0)
                if fcm_result.get('failure_count', 0) > 0:
                    fcm_failure_count += fcm_result.get('failure_count', 0)
                
                # Check if user has FCM tokens
                from api.models import FCMDeviceToken
                token_count = FCMDeviceToken.objects.filter(user=user, is_active=True).count()
                if token_count == 0:
                    logger.warning(f"User {user.user_id} has no active FCM tokens registered")
                
                sent_count += 1
            except Exception as e:
                error_msg = f"Failed to send notification to user {user.user_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        # Count users with FCM tokens
        from api.models import FCMDeviceToken
        users_with_tokens = FCMDeviceToken.objects.filter(
            user__in=recipients,
            is_active=True
        ).values('user').distinct().count()
        
        message = f'In-app notifications created for {sent_count} users. '
        if fcm_success_count > 0:
            message += f'FCM push notifications sent successfully to {fcm_success_count} device(s). '
        if fcm_failure_count > 0:
            message += f'{fcm_failure_count} device(s) failed to receive. '
        if users_with_tokens < sent_count:
            message += f'Note: {sent_count - users_with_tokens} user(s) have no registered FCM tokens (they need to log in on their device).'
        if errors:
            message += f' Errors: {len(errors)}'
        
        return Response({
            'status': True,
            'message': message,
            'sent_count': sent_count,
            'fcm_success_count': fcm_success_count,
            'fcm_failure_count': fcm_failure_count,
            'total_users': recipients.count(),
            'users_with_tokens': users_with_tokens,
            'errors': errors if errors else None
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending push notifications: {str(e)}", exc_info=True)
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Crypto Wallets endpoints
@api_view(['GET'])
@require_admin_auth
def admin_crypto_wallets(request):
    """Get all crypto ledger wallets"""
    try:
        wallets = CryptoLedger.objects.select_related('user').all().order_by('-timestamp')
        
        wallets_data = []
        for wallet in wallets:
            wallets_data.append({
                'uniq_id': wallet.uniq_id,
                'user_id': wallet.user.user_id,
                'asset': wallet.asset,
                'asset_chain': wallet.asset_chain,
                'public_key': wallet.public_key[:50] + '...' if len(wallet.public_key) > 50 else wallet.public_key,
                'balance': str(wallet.balance),
                'last_checked': wallet.last_checked.isoformat() if wallet.last_checked else None,
                'timestamp': wallet.timestamp.isoformat() if wallet.timestamp else None,
            })
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'wallets': wallets_data,
                'total': len(wallets_data)
            }
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_crypto_wallet_keys(request, wallet_id):
    """Get decrypted public and private keys for a crypto wallet"""
    try:
        from api.external.encryption import Encryption
        
        wallet = CryptoLedger.objects.get(uniq_id=wallet_id)
        cipher = Encryption()
        
        # Decrypt public key
        try:
            if isinstance(wallet.public_key, str):
                if wallet.public_key.startswith("b'") or wallet.public_key.startswith('b"'):
                    import ast
                    encrypted_key = ast.literal_eval(wallet.public_key)
                else:
                    encrypted_key = wallet.public_key.encode('utf-8')
            else:
                encrypted_key = wallet.public_key
            
            decrypted_public_key = cipher.decrypt(encrypted_key)
        except Exception as e:
            try:
                decrypted_public_key = cipher.decrypt(wallet.public_key)
            except:
                decrypted_public_key = str(wallet.public_key)
        
        # For USDC wallets, the public_key stores the Circle wallet_id, not the address
        # We need to fetch the actual address from Circle API
        if wallet.asset == 'USDC':
            try:
                from api.crypto.circle_usdc import CircleUSDC
                circle_usdc = CircleUSDC()
                wallet_info = circle_usdc.get_wallet(decrypted_public_key)  # decrypted_public_key is the wallet_id
                actual_address = wallet_info['data']['wallet']['address']
                decrypted_public_key = actual_address
            except Exception as e:
                # If Circle API call fails, return the wallet_id with a note
                decrypted_public_key = f"{decrypted_public_key} (Error fetching address: {str(e)})"
        
        # Decrypt private key
        try:
            if isinstance(wallet.private_key, str):
                if wallet.private_key.startswith("b'") or wallet.private_key.startswith('b"'):
                    import ast
                    encrypted_key = ast.literal_eval(wallet.private_key)
                else:
                    encrypted_key = wallet.private_key.encode('utf-8')
            else:
                encrypted_key = wallet.private_key
            
            decrypted_private_key = cipher.decrypt(encrypted_key)
        except Exception as e:
            try:
                decrypted_private_key = cipher.decrypt(wallet.private_key)
            except:
                decrypted_private_key = str(wallet.private_key)
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0
        try:
            wallet_balance = float(calculate_total_balance(wallet.user))
        except Exception as e:
            print(f"Error calculating balance: {e}")
            pass

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'public_key': decrypted_public_key,
                'private_key': decrypted_private_key,
                'asset': wallet.asset,
                'asset_chain': wallet.asset_chain,
            }
        })
    except CryptoLedger.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Wallet not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_crypto_wallet_check_balance(request, wallet_id):
    """Check balance for a single crypto wallet"""
    try:
        from api.crypto.circle_usdc import CircleUSDC
        from api.crypto.stellar import StellarWallet
        from api.external.encryption import Encryption
        from decimal import Decimal
        
        wallet = CryptoLedger.objects.get(uniq_id=wallet_id)
        cipher = Encryption()
        
        # Decrypt public key to get wallet address
        wallet_address = StellarWallet._decrypt_key(wallet.public_key)
        
        current_balance = Decimal('0')
        
        # Check balance based on asset type
        if wallet.asset == 'USDC':
            circle_usdc = CircleUSDC()
            current_balance = Decimal(str(circle_usdc.get_balance(wallet_address, asset_code='USDC')))
        elif wallet.asset == 'XLM':
            stellar_wallet = StellarWallet()
            current_balance = Decimal(str(stellar_wallet.get_balance(wallet_address)))
        else:
            return Response({
                'status': False,
                'message': f'Unsupported asset: {wallet.asset}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update wallet balance
        wallet.balance = current_balance
        wallet.last_checked = timezone.now()
        wallet.save()
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0
        try:
            wallet_balance = float(calculate_total_balance(wallet.user))
        except Exception as e:
            print(f"Error calculating balance: {e}")
            pass

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'balance': str(current_balance),
                'asset': wallet.asset
            }
        })
    except CryptoLedger.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Wallet not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_crypto_wallets_check_all_balances(request):
    """Check balances for multiple wallets"""
    try:
        from api.crypto.circle_usdc import CircleUSDC
        from api.crypto.stellar import StellarWallet
        from api.external.encryption import Encryption
        from decimal import Decimal
        
        wallet_ids = request.data.get('wallet_ids', [])
        
        if not wallet_ids:
            wallets = CryptoLedger.objects.all()
        else:
            wallets = CryptoLedger.objects.filter(uniq_id__in=wallet_ids)
        
        cipher = Encryption()
        circle_usdc = CircleUSDC()
        stellar_wallet = StellarWallet()
        
        checked = 0
        errors = 0
        
        for wallet in wallets:
            try:
                # Decrypt public key
                wallet_address = StellarWallet._decrypt_key(wallet.public_key)
                
                current_balance = Decimal('0')
                
                if wallet.asset == 'USDC':
                    current_balance = Decimal(str(circle_usdc.get_balance(wallet_address, asset_code='USDC')))
                elif wallet.asset == 'XLM':
                    current_balance = Decimal(str(stellar_wallet.get_balance(wallet_address)))
                else:
                    errors += 1
                    continue
                
                wallet.balance = current_balance
                wallet.last_checked = timezone.now()
                wallet.save()
                checked += 1
            except Exception as e:
                print(f"Error checking balance for wallet {wallet.uniq_id}: {str(e)}")
                errors += 1
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'checked': checked,
                'errors': errors
            }
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_crypto_wallet_sweep(request, wallet_id):
    """Sweep a single crypto wallet to target wallet"""
    try:
        from api.crypto.circle_usdc import CircleUSDC
        from api.crypto.stellar import StellarWallet
        from api.external.encryption import Encryption
        from decimal import Decimal
        
        wallet = CryptoLedger.objects.get(uniq_id=wallet_id)
        
        # Get target sweep wallet
        try:
            sweep_wallet = CryptoLedgerSweepWallet.objects.get(
                asset=wallet.asset,
                asset_chain=wallet.asset_chain,
                is_active=True
            )
        except CryptoLedgerSweepWallet.DoesNotExist:
            return Response({
                'status': False,
                'message': f'No sweep wallet configured for {wallet.asset} on {wallet.asset_chain}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if wallet.balance <= 0:
            return Response({
                'status': False,
                'message': 'Wallet has no balance to sweep'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cipher = Encryption()
        
        # Decrypt keys
        try:
            source_private_key = cipher.decrypt(wallet.private_key.encode('utf-8') if isinstance(wallet.private_key, str) else wallet.private_key)
            source_public_key = cipher.decrypt(wallet.public_key.encode('utf-8') if isinstance(wallet.public_key, str) else wallet.public_key)
            target_public_key = cipher.decrypt(sweep_wallet.public_key.encode('utf-8') if isinstance(sweep_wallet.public_key, str) else sweep_wallet.public_key)
        except:
            source_private_key = cipher.decrypt(wallet.private_key)
            source_public_key = cipher.decrypt(wallet.public_key)
            target_public_key = cipher.decrypt(sweep_wallet.public_key)
        
        amount_to_sweep = wallet.balance
        
        # Perform sweep based on asset type using sweep_funds method
        if wallet.asset == 'USDC':
            circle_usdc = CircleUSDC()
            result = circle_usdc.sweep_funds(
                user_id=wallet.user.user_id,
                asset=wallet.asset,
                chain=wallet.asset_chain,
                destination_wallet=target_public_key
            )
        elif wallet.asset == 'XLM':
            stellar_wallet = StellarWallet()
            result = stellar_wallet.sweep_funds(
                user_id=wallet.user.user_id,
                asset=wallet.asset,
                chain=wallet.asset_chain,
                destination_wallet=target_public_key
            )
        else:
            return Response({
                'status': False,
                'message': f'Unsupported asset: {wallet.asset}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if result.get('status'):
            # Update wallet balance
            wallet.balance = Decimal('0')
            wallet.last_checked = timezone.now()
            wallet.save()
            
            return Response({
                'status': True,
                'data': {
                    'amount': str(amount_to_sweep),
                    'asset': wallet.asset,
                    'transaction_id': result.get('transaction_id') or result.get('transaction_hash')
                }
            })
        else:
            return Response({
                'status': False,
                'message': result.get('message', 'Failed to sweep wallet')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except CryptoLedger.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Wallet not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_crypto_wallets_sweep_all(request):
    """Sweep multiple crypto wallets"""
    try:
        from api.crypto.circle_usdc import CircleUSDC
        from api.crypto.stellar import StellarWallet
        from api.external.encryption import Encryption
        from decimal import Decimal
        
        wallet_ids = request.data.get('wallet_ids', [])
        
        if not wallet_ids:
            wallets = CryptoLedger.objects.filter(balance__gt=0)
        else:
            wallets = CryptoLedger.objects.filter(uniq_id__in=wallet_ids, balance__gt=0)
        
        cipher = Encryption()
        circle_usdc = CircleUSDC()
        stellar_wallet = StellarWallet()
        
        swept = 0
        errors = 0
        total_amount = Decimal('0')
        
        for wallet in wallets:
            try:
                # Get target sweep wallet
                try:
                    sweep_wallet = CryptoLedgerSweepWallet.objects.get(
                        asset=wallet.asset,
                        asset_chain=wallet.asset_chain,
                        is_active=True
                    )
                except CryptoLedgerSweepWallet.DoesNotExist:
                    errors += 1
                    continue
                
                if wallet.balance <= 0:
                    continue
                
                # Decrypt source wallet keys and target sweep wallet public key
                try:
                    source_private_key = cipher.decrypt(wallet.private_key.encode('utf-8') if isinstance(wallet.private_key, str) else wallet.private_key)
                    target_public_key = cipher.decrypt(sweep_wallet.public_key.encode('utf-8') if isinstance(sweep_wallet.public_key, str) else sweep_wallet.public_key)
                except:
                    source_private_key = cipher.decrypt(wallet.private_key)
                    target_public_key = cipher.decrypt(sweep_wallet.public_key)
                
                amount_to_sweep = wallet.balance
                
                # Perform sweep using sweep_funds method
                if wallet.asset == 'USDC':
                    result = circle_usdc.sweep_funds(
                        user_id=wallet.user.user_id,
                        asset=wallet.asset,
                        chain=wallet.asset_chain,
                        destination_wallet=target_public_key
                    )
                elif wallet.asset == 'XLM':
                    result = stellar_wallet.sweep_funds(
                        user_id=wallet.user.user_id,
                        asset=wallet.asset,
                        chain=wallet.asset_chain,
                        destination_wallet=target_public_key
                    )
                else:
                    errors += 1
                    continue
                
                if result.get('status'):
                    wallet.balance = Decimal('0')
                    wallet.last_checked = timezone.now()
                    wallet.save()
                    swept += 1
                    total_amount += amount_to_sweep
                else:
                    errors += 1
            except Exception as e:
                print(f"Error sweeping wallet {wallet.uniq_id}: {str(e)}")
                errors += 1
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'swept': swept,
                'errors': errors,
                'total_amount': str(total_amount)
            }
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Sweep Wallet Configuration endpoints
@api_view(['GET'])
@require_admin_auth
def admin_sweep_wallets(request):
    """Get all configured sweep wallets"""
    try:
        from api.external.encryption import Encryption
        
        sweep_wallets = CryptoLedgerSweepWallet.objects.all().order_by('asset', 'asset_chain')
        cipher = Encryption()
        
        wallets_data = []
        for wallet in sweep_wallets:
            # Decrypt public key
            try:
                if isinstance(wallet.public_key, str):
                    if wallet.public_key.startswith("b'") or wallet.public_key.startswith('b"'):
                        import ast
                        encrypted_key = ast.literal_eval(wallet.public_key)
                        decrypted_public_key = cipher.decrypt(encrypted_key)
                    else:
                        # Try to decrypt as string first
                        try:
                            decrypted_public_key = cipher.decrypt(wallet.public_key.encode('utf-8'))
                        except:
                            decrypted_public_key = cipher.decrypt(wallet.public_key)
                else:
                    decrypted_public_key = cipher.decrypt(wallet.public_key)
            except Exception as e:
                try:
                    decrypted_public_key = cipher.decrypt(wallet.public_key)
                except:
                    decrypted_public_key = str(wallet.public_key)
            
            wallets_data.append({
                'uniq_id': wallet.uniq_id,
                'asset': wallet.asset,
                'asset_chain': wallet.asset_chain,
                'public_key': decrypted_public_key,
                'is_active': wallet.is_active,
                'description': wallet.description,
                'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
                'updated_at': wallet.updated_at.isoformat() if wallet.updated_at else None,
            })
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'wallets': wallets_data,
                'total': len(wallets_data)
            }
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_sweep_wallet_create(request):
    """Create a new sweep wallet configuration"""
    try:
        from api.external.encryption import Encryption
        
        asset = request.data.get('asset')
        asset_chain = request.data.get('asset_chain')
        public_key = request.data.get('public_key')
        description = request.data.get('description', '')
        is_active = request.data.get('is_active', True)
        
        if not all([asset, asset_chain, public_key]):
            return Response({
                'status': False,
                'message': 'asset, asset_chain, and public_key are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if sweep wallet already exists for this asset/chain
        if CryptoLedgerSweepWallet.objects.filter(asset=asset, asset_chain=asset_chain).exists():
            return Response({
                'status': False,
                'message': f'Sweep wallet already exists for {asset} on {asset_chain}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Encrypt public key for storage
        cipher = Encryption()
        # Ensure public_key is a string before encrypting
        if isinstance(public_key, bytes):
            public_key = public_key.decode('utf-8')
        encrypted_public_key = cipher.encrypt(public_key)
        
        # Convert encrypted bytes to string for storage
        if isinstance(encrypted_public_key, bytes):
            encrypted_public_key = str(encrypted_public_key)
        
        sweep_wallet = CryptoLedgerSweepWallet.objects.create(
            asset=asset,
            asset_chain=asset_chain,
            public_key=encrypted_public_key,
            description=description,
            is_active=is_active
        )
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'uniq_id': sweep_wallet.uniq_id,
                'asset': sweep_wallet.asset,
                'asset_chain': sweep_wallet.asset_chain,
                'is_active': sweep_wallet.is_active
            },
            'message': 'Sweep wallet created successfully'
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT', 'DELETE'])
@csrf_exempt
@require_admin_auth
def admin_sweep_wallet_update(request, sweep_wallet_id):
    """Update or delete a sweep wallet configuration"""
    try:
        from api.external.encryption import Encryption
        
        sweep_wallet = CryptoLedgerSweepWallet.objects.get(uniq_id=sweep_wallet_id)
        
        if request.method == 'DELETE':
            sweep_wallet.delete()
            return Response({
                'status': True,
                'message': 'Sweep wallet deleted successfully'
            })
        
        # Update
        public_key = request.data.get('public_key')
        description = request.data.get('description')
        is_active = request.data.get('is_active')
        
        if public_key is not None:
            cipher = Encryption()
            # Ensure public_key is a string before encrypting
            if isinstance(public_key, bytes):
                public_key = public_key.decode('utf-8')
            encrypted_public_key = cipher.encrypt(public_key)
            if isinstance(encrypted_public_key, bytes):
                encrypted_public_key = str(encrypted_public_key)
            sweep_wallet.public_key = encrypted_public_key
        
        if description is not None:
            sweep_wallet.description = description
        
        if is_active is not None:
            sweep_wallet.is_active = bool(is_active)
        
        sweep_wallet.save()
        
        # Calculate fiat wallet balance
        wallet_balance = 0.0

        return Response({
            'status': True,
            'data': {
                'wallet_balance': wallet_balance,
                'uniq_id': sweep_wallet.uniq_id,
                'asset': sweep_wallet.asset,
                'asset_chain': sweep_wallet.asset_chain,
                'is_active': sweep_wallet.is_active
            },
            'message': 'Sweep wallet updated successfully'
        })
    except CryptoLedgerSweepWallet.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Sweep wallet not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@require_admin_auth
def admin_list_plans(request):
    """Get list of all subscription plans"""
    plans = SubscriptionPlans.objects.all().order_by('uniq_id')
    plans_data = []
    for plan in plans:
        plans_data.append({
            'id': plan.uniq_id,
            'plan_name': plan.plan_name,
            'inventory': plan.inventory,
            'collection_accounts': plan.collection_accounts,
            'ai_manager': plan.ai_manager,
            'managers': getattr(plan, 'managers', 1),
            'cashiers': plan.cashiers,
            'max_products': plan.max_products,
            'business_reporting': plan.business_reporting,
            'installment_payment': plan.installment_payment,
            'online_store': plan.online_store,
            'payroll': plan.payroll,
            'support': plan.support,
            'description': plan.description,
            'is_popular': plan.is_popular,
            'one_amount': plan.one_amount,
            'three_months': plan.three_months,
            'six_months': plan.six_months,
            'twelve_months': plan.twelve_months,
        })
    
    return Response({
        'status': True,
        'data': plans_data
    })

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_create_plan(request):
    """Create a new subscription plan"""
    try:
        plan = SubscriptionPlans.objects.create(
            plan_name=request.data.get('plan_name'),
            inventory=request.data.get('inventory', True),
            collection_accounts=request.data.get('collection_accounts'),
            ai_manager=request.data.get('ai_manager', False),
            managers=request.data.get('managers', 1),
            cashiers=request.data.get('cashiers', 1),
            max_products=request.data.get('max_products', 10),
            business_reporting=request.data.get('business_reporting', False),
            installment_payment=request.data.get('installment_payment', False),
            online_store=request.data.get('online_store', False),
            payroll=request.data.get('payroll'),
            support=request.data.get('support', True),
            description=request.data.get('description'),
            is_popular=request.data.get('is_popular', False),
            one_amount=request.data.get('one_amount'),
            three_months=request.data.get('three_months'),
            six_months=request.data.get('six_months'),
            twelve_months=request.data.get('twelve_months'),
        )
        return Response({
            'status': True,
            'message': 'Subscription plan created successfully'
        })
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT', 'DELETE'])
@csrf_exempt
@require_admin_auth
def admin_plan_update(request, plan_id):
    """Update or delete a subscription plan"""
    try:
        plan = SubscriptionPlans.objects.get(uniq_id=plan_id)
        
        if request.method == 'DELETE':
            plan.delete()
            return Response({
                'status': True,
                'message': 'Subscription plan deleted successfully'
            })
        
        # Update
        plan.plan_name = request.data.get('plan_name', plan.plan_name)
        plan.inventory = request.data.get('inventory', plan.inventory)
        plan.collection_accounts = request.data.get('collection_accounts', plan.collection_accounts)
        plan.ai_manager = request.data.get('ai_manager', plan.ai_manager)
        plan.managers = request.data.get('managers', getattr(plan, 'managers', 1))
        plan.cashiers = request.data.get('cashiers', plan.cashiers)
        plan.max_products = request.data.get('max_products', plan.max_products)
        plan.business_reporting = request.data.get('business_reporting', plan.business_reporting)
        plan.installment_payment = request.data.get('installment_payment', plan.installment_payment)
        plan.online_store = request.data.get('online_store', plan.online_store)
        plan.payroll = request.data.get('payroll', plan.payroll)
        plan.support = request.data.get('support', plan.support)
        plan.description = request.data.get('description', plan.description)
        plan.is_popular = request.data.get('is_popular', plan.is_popular)
        plan.one_amount = request.data.get('one_amount', plan.one_amount)
        plan.three_months = request.data.get('three_months', plan.three_months)
        plan.six_months = request.data.get('six_months', plan.six_months)
        plan.twelve_months = request.data.get('twelve_months', plan.twelve_months)
        
        plan.save()
        
        return Response({
            'status': True,
            'message': 'Subscription plan updated successfully'
        })
    except SubscriptionPlans.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Subscription plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@require_admin_auth
def admin_stores_api(request):
    """Get paginated list of stores"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))
    search = request.GET.get('search', '')
    
    stores_query = BusinessDetails.objects.filter(store_setup=True).select_related('user').prefetch_related('user__details').order_by('-id')
    
    if search:
        stores_query = stores_query.filter(
            Q(business_name__icontains=search) |
            Q(store_slug__icontains=search) |
            Q(user__user_email__icontains=search) |
            Q(user__user_id__icontains=search)
        )
    
    paginator = Paginator(stores_query, per_page)
    page_obj = paginator.get_page(page)
    
    stores_data = []
    for store in page_obj:
        user = store.user
        owner_name = "N/A"
        owner_email = ""
        owner_id = ""
        timestamp = None
        
        if user:
            owner_email = user.user_email or ""
            owner_id = user.user_id or ""
            if user.date_created:
                try:
                    timestamp = datetime.fromtimestamp(user.date_created).isoformat()
                except:
                    timestamp = None
            details = user.details.first()
            if details and (details.first_name or details.last_name):
                owner_name = f"{details.first_name or ''} {details.last_name or ''}".strip()
            elif owner_email:
                owner_name = owner_email.split('@')[0]
                
        stores_data.append({
            'id': store.id,
            'business_name': store.business_name or "Unnamed Store",
            'business_type': store.business_type or "N/A",
            'store_slug': store.store_slug or "",
            'store_custom_domain': store.store_custom_domain,
            'store_setup': store.store_setup,
            'timestamp': timestamp,
            'owner_name': owner_name,
            'owner_email': owner_email,
            'owner_id': owner_id,
            'ad_credit': float(store.ad_credit or 0.00),
        })
    
    return Response({
        'status': True,
        'data': stores_data,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'total_records': paginator.count,
            'per_page': per_page,
            'start_index': page_obj.start_index() if paginator.count > 0 else 0,
            'end_index': page_obj.end_index() if paginator.count > 0 else 0,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })

def admin_grant_ad_credit(request):
    """Grant or update ad credit for selected stores (single or batch)"""
    if not check_admin_auth(request):
        return JsonResponse({'status': False, 'message': 'Unauthorized'}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)
    
    try:
        data = None
        if hasattr(request, 'data') and isinstance(request.data, dict):
            data = request.data
        elif request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
                if isinstance(data, str):
                    data = json.loads(data)
            except Exception:
                data = request.POST
        if not data or not isinstance(data, dict):
            data = request.POST or {}
            
        store_ids = data.get('store_ids', [])
        if isinstance(store_ids, (int, str)):
            store_ids = [store_ids]
        
        if not store_ids:
            return JsonResponse({'status': False, 'message': 'No stores selected'}, status=400)
        
        amount_raw = data.get('amount', 0)
        try:
            amount_ngn = Decimal(str(amount_raw))
        except Exception:
            return JsonResponse({'status': False, 'message': 'Invalid credit amount'}, status=400)
            
        if amount_ngn <= 0:
            return JsonResponse({'status': False, 'message': 'Credit amount must be greater than 0'}, status=400)
            
        action = data.get('action', 'add') # 'add' or 'set'
        note = str(data.get('note', '')).strip()
        
        from api.user_data.domain_views import get_exchange_rate
        
        stores = BusinessDetails.objects.filter(id__in=store_ids)
        updated_count = 0
        rates_cache = {'NGN': Decimal('1.0')}
        
        for store in stores:
            user_details = UserDetails.objects.filter(user=store.user).first()
            user_currency = user_details.currency if user_details and user_details.currency else 'NGN'
            
            if user_currency not in rates_cache:
                try:
                    rate_float = get_exchange_rate('NGN', user_currency)
                    rates_cache[user_currency] = Decimal(str(rate_float))
                except Exception as e:
                    logger.error(f"Exchange rate error for {user_currency}: {e}")
                    rates_cache[user_currency] = Decimal('1.0') # Fallback if API fails
            
            rate = rates_cache[user_currency]
            converted_amount = amount_ngn * rate
            
            if action == 'set':
                store.ad_credit = converted_amount
            else:
                store.ad_credit = (store.ad_credit or Decimal('0.00')) + converted_amount
            store.save(update_fields=['ad_credit'])
            updated_count += 1
            
            # Send congratulatory email to store owner
            if store.user:
                try:
                    from api.tasks import send_ad_credit_awarded_email
                    send_ad_credit_awarded_email.apply_async(
                        args=[
                            store.user.user_id,
                            float(converted_amount),
                            user_currency,
                            float(store.ad_credit),
                            store.business_name or ''
                        ]
                    )
                except Exception as email_err:
                    logger.error(f"Failed to enqueue ad credit awarded email for user {store.user.user_id}: {email_err}")
            
        return JsonResponse({
            'status': True,
            'message': f'Successfully {"set" if action == "set" else "added"} ₦{amount_ngn:,.2f} ad credit for {updated_count} store(s).',
            'updated_count': updated_count
        })
    except Exception as e:
        logger.error(f"Error granting ad credit: {str(e)}")
        return JsonResponse({'status': False, 'message': str(e)}, status=500)

def admin_stores_page(request):
    """Admin stores management page"""
    if not check_admin_auth(request):
        return redirect('/admin/login/')
    return render(request, 'admin/stores.html')

def admin_allowed_countries_page(request):
    """Admin regional settings page"""
    if not check_admin_auth(request):
        return redirect('/admin/login/')
    return render(request, 'admin/allowed-countries.html')

def admin_careers_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            JobPosition.objects.filter(id=request.POST.get('id')).delete()
        elif action == 'create':
            JobPosition.objects.create(
                title=request.POST.get('title'),
                department=request.POST.get('department'),
                location=request.POST.get('location'),
                job_type=request.POST.get('job_type'),
                description=request.POST.get('description')
            )
        elif action == 'update':
            JobPosition.objects.filter(id=request.POST.get('id')).update(
                title=request.POST.get('title'),
                department=request.POST.get('department'),
                location=request.POST.get('location'),
                job_type=request.POST.get('job_type'),
                description=request.POST.get('description')
            )
        return redirect('admin_careers_page')
        
    jobs = JobPosition.objects.all().order_by('-created_at')
    return render(request, 'admin/careers.html', {'jobs': jobs})

def admin_job_applications_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            JobApplication.objects.filter(id=request.POST.get('id')).delete()
        return redirect('admin_job_applications_page')
        
    applications = JobApplication.objects.all().order_by('-applied_at')
    return render(request, 'admin/job_applications.html', {'applications': applications})

def admin_team_members_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            TeamMember.objects.filter(id=request.POST.get('id')).delete()
        elif action == 'create':
            member = TeamMember.objects.create(
                name=request.POST.get('name'),
                role=request.POST.get('role'),
                department=request.POST.get('department'),
                order=request.POST.get('order', 0)
            )
            if request.FILES.get('image'):
                member.image = request.FILES.get('image')
                member.save()
        elif action == 'update':
            member_id = request.POST.get('id')
            TeamMember.objects.filter(id=member_id).update(
                name=request.POST.get('name'),
                role=request.POST.get('role'),
                department=request.POST.get('department'),
                order=request.POST.get('order', 0)
            )
            if request.FILES.get('image'):
                member = TeamMember.objects.get(id=member_id)
                member.image = request.FILES.get('image')
                member.save()
        return redirect('admin_team_members_page')
        
    members = TeamMember.objects.all().order_by('order')
    return render(request, 'admin/team_members.html', {'members': members})

def admin_site_settings_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    settings = SiteSettings.load()
    
    if request.method == 'POST':
        action = request.POST.get('action', 'update_settings')
        if action == 'add_blog_cat':
            name = request.POST.get('name')
            if name: BlogCategory.objects.get_or_create(name=name)
        elif action == 'del_blog_cat':
            BlogCategory.objects.filter(id=request.POST.get('id')).delete()
        elif action == 'add_help_cat':
            name = request.POST.get('name')
            if name: HelpCategory.objects.get_or_create(name=name)
        elif action == 'del_help_cat':
            HelpCategory.objects.filter(id=request.POST.get('id')).delete()
        elif action == 'update_settings':
            settings.email = request.POST.get('email', settings.email)
            settings.phone = request.POST.get('phone', settings.phone)
            settings.address = request.POST.get('address', settings.address)
            settings.working_hours = request.POST.get('working_hours', settings.working_hours)
            settings.map_embed_url = request.POST.get('map_embed_url', settings.map_embed_url)
            settings.map_directions_url = request.POST.get('map_directions_url', settings.map_directions_url)
            settings.twitter_url = request.POST.get('twitter_url', settings.twitter_url)
            settings.linkedin_url = request.POST.get('linkedin_url', settings.linkedin_url)
            settings.instagram_url = request.POST.get('instagram_url', settings.instagram_url)
            settings.facebook_url = request.POST.get('facebook_url', settings.facebook_url)
            
            # Promo settings
            settings.promo_banner_enabled = request.POST.get('promo_banner_enabled') == 'true'
            promo_plan_id = request.POST.get('promo_plan')
            if promo_plan_id:
                try:
                    settings.promo_plan = SubscriptionPlans.objects.get(uniq_id=promo_plan_id)
                except SubscriptionPlans.DoesNotExist:
                    settings.promo_plan = None
            else:
                settings.promo_plan = None
            settings.promo_duration = request.POST.get('promo_duration', settings.promo_duration)
            
            # AI Settings
            image_cost = request.POST.get('user_image_generation_cost_usd')
            if image_cost is not None:
                try:
                    settings.user_image_generation_cost_usd = float(image_cost)
                except ValueError:
                    pass
            
            ai_model = request.POST.get('ai_generation_model')
            if ai_model:
                settings.ai_generation_model = ai_model

            video_cost = request.POST.get('user_video_generation_cost_usd')
            if video_cost is not None:
                try:
                    settings.user_video_generation_cost_usd = float(video_cost)
                except ValueError:
                    pass
            
            ai_video_model = request.POST.get('ai_video_generation_model')
            if ai_video_model:
                settings.ai_video_generation_model = ai_video_model
            
            settings.save()
        elif action == 'update_theme_prices':
            from api.models import PremiumStoreLayout
            for layout in PremiumStoreLayout.objects.all():
                price_key = f"price_{layout.layout_id}"
                active_key = f"active_{layout.layout_id}"
                if price_key in request.POST:
                    try:
                        layout.price_ngn = float(request.POST[price_key])
                    except (ValueError, TypeError):
                        pass
                layout.is_active = (request.POST.get(active_key) == 'true')
                layout.save()
        return redirect('admin_site_settings_page')
        
    blog_categories = BlogCategory.objects.all()
    help_categories = HelpCategory.objects.all()
    plans = SubscriptionPlans.objects.all()
    
    from api.models import PremiumStoreLayout
    PremiumStoreLayout.objects.get_or_create(layout_id='luxe-horizon', defaults={'name': 'Horizon Luxe', 'price_ngn': 20000.00, 'is_active': True})
    PremiumStoreLayout.objects.get_or_create(layout_id='vanguard-atelier', defaults={'name': 'Atelier Vanguard', 'price_ngn': 25000.00, 'is_active': True})
    PremiumStoreLayout.objects.get_or_create(layout_id='metro-pulse', defaults={'name': 'Metro Pulse', 'price_ngn': 18000.00, 'is_active': True})
    PremiumStoreLayout.objects.get_or_create(layout_id='folio-press', defaults={'name': 'Folio Press', 'price_ngn': 22000.00, 'is_active': True})
    PremiumStoreLayout.objects.get_or_create(layout_id='premium-commerce-editorial', defaults={'name': 'Premium Commerce Editorial', 'price_ngn': 28000.00, 'is_active': True})
    premium_layouts = PremiumStoreLayout.objects.all().order_by('name')

    return render(request, 'admin/site_settings.html', {
        'settings': settings,
        'blog_categories': blog_categories,
        'help_categories': help_categories,
        'plans': plans,
        'premium_layouts': premium_layouts
    })

def admin_contact_messages_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        msg_id = request.POST.get('id')
        
        if msg_id:
            try:
                msg = ContactMessage.objects.get(id=msg_id)
                if action == 'delete':
                    msg.delete()
                elif action in ['pending', 'ongoing', 'resolved']:
                    msg.status = action
                    msg.save()
            except ContactMessage.DoesNotExist:
                pass
        return redirect('admin_contact_messages_page')
        
    status_filter = request.GET.get('status', 'all')
    
    if status_filter != 'all':
        messages_list = ContactMessage.objects.filter(status=status_filter)
    else:
        messages_list = ContactMessage.objects.all()
        
    return render(request, 'admin/contact_messages.html', {
        'messages': messages_list,
        'current_filter': status_filter
    })

from django.utils.text import slugify

def admin_help_articles_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            HelpArticle.objects.filter(uniq_id=request.POST.get('id')).delete()
        return redirect('admin_help_articles_page')
        
    articles = HelpArticle.objects.all().order_by('-timestamp')
    return render(request, 'admin/help_articles.html', {'articles': articles})

def admin_help_article_form(request, article_id=None):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    article = None
    if article_id:
        article = HelpArticle.objects.filter(uniq_id=article_id).first()
        
    if request.method == 'POST':
        title = request.POST.get('title')
        slug = request.POST.get('slug') or slugify(title)
        category_id = request.POST.get('category_id')
        category = HelpCategory.objects.filter(id=category_id).first() if category_id else None
        youtube_video_url = request.POST.get('youtube_video_url', '')
        content = request.POST.get('content')
        
        if article:
            article.title = title
            article.slug = slug
            article.category = category
            article.youtube_video_url = youtube_video_url
            article.content = content
            article.save()
        else:
            HelpArticle.objects.create(
                title=title,
                slug=slug,
                category=category,
                youtube_video_url=youtube_video_url,
                content=content
            )
        return redirect('admin_help_articles_page')
        
    categories = HelpCategory.objects.all()
    return render(request, 'admin/help_article_form.html', {'article': article, 'categories': categories})

def admin_blog_posts_page(request):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            BlogPost.objects.filter(uniq_id=request.POST.get('id')).delete()
        return redirect('admin_blog_posts_page')
        
    posts = BlogPost.objects.all().order_by('-timestamp')
    return render(request, 'admin/blog_posts.html', {'posts': posts})

def admin_blog_post_form(request, post_id=None):
    if not check_admin_auth(request):
        return redirect('/admin/login/')
        
    post = None
    if post_id:
        post = BlogPost.objects.filter(uniq_id=post_id).first()
        
    if request.method == 'POST':
        title = request.POST.get('title')
        slug = request.POST.get('slug') or slugify(title)
        category_id = request.POST.get('category_id')
        category = BlogCategory.objects.filter(id=category_id).first() if category_id else None
        summary = request.POST.get('summary', '')
        image = request.FILES.get('image')
        is_published = request.POST.get('is_published') == 'on'
        content = request.POST.get('content')
        
        if post:
            post.title = title
            post.slug = slug
            post.category = category
            post.summary = summary
            if image:
                post.image = image
            post.is_published = is_published
            post.content = content
            post.save()
        else:
            BlogPost.objects.create(
                title=title,
                slug=slug,
                category=category,
                summary=summary,
                image=image,
                is_published=is_published,
                content=content
            )
        return redirect('admin_blog_posts_page')
        
    categories = BlogCategory.objects.all()
    return render(request, 'admin/blog_post_form.html', {'post': post, 'categories': categories})


@api_view(['GET'])
@require_admin_auth
def admin_user_wallets(request, user_id):
    """Get user crypto wallets"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        wallets = CryptoLedger.objects.filter(user=user)
        
        encryptor = Encryption()
        wallets_data = []
        for wallet in wallets:
            pub_key_str = wallet.public_key or ""
            decrypted_public_key = pub_key_str
            if pub_key_str:
                try:
                    if pub_key_str.startswith("b'") and pub_key_str.endswith("'"):
                        pub_key_bytes = pub_key_str[2:-1].encode()
                    else:
                        pub_key_bytes = pub_key_str.encode()
                    decrypted_public_key = encryptor.decrypt(pub_key_bytes)
                except Exception:
                    pass
                
            wallets_data.append({
                'id': str(wallet.uniq_id),
                'asset': wallet.asset,
                'asset_chain': wallet.asset_chain,
                'public_key': decrypted_public_key or pub_key_str,
                'balance': wallet.balance,
                'last_checked': wallet.last_checked.isoformat() if wallet.last_checked else None,
            })
            
        return Response({
            'status': True,
            'data': wallets_data
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@csrf_exempt
@require_admin_auth
def admin_delete_user_wallet(request, user_id, wallet_id):
    """Delete user crypto wallet"""
    try:
        user = UserSecure.objects.get(user_id=user_id)
        wallet = CryptoLedger.objects.get(user=user, uniq_id=wallet_id)
        wallet.delete()
        
        return Response({
            'status': True,
            'message': 'Wallet deleted successfully'
        })
    except UserSecure.DoesNotExist:
        return Response({
            'status': False,
            'message': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except CryptoLedger.DoesNotExist:
        return Response({
            'status': False,
            'message': 'Wallet not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'status': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@require_admin_auth
def admin_backers_page(request):
    backers = Backer.objects.all()
    return render(request, "admin/backers.html", {"backers": backers})

@require_admin_auth
def admin_backers(request):
    if request.method == 'GET':
        backers = Backer.objects.all()
        data = []
        for b in backers:
            data.append({
                'id': b.id,
                'name': b.name,
                'logo_url': b.logo.url if b.logo else None,
                'url': b.url,
                'is_active': b.is_active,
                'created_at': b.created_at.isoformat()
            })
        return JsonResponse({'status': 'success', 'backers': data})
        
    elif request.method == 'POST':
        name = request.POST.get('name')
        url = request.POST.get('url')
        is_active = request.POST.get('is_active') == 'true'
        logo = request.FILES.get('logo')
        
        if 'name' in request.POST:
            pass # Name is optional
        backer = Backer.objects.create(
            name=name,
            url=url,
            is_active=is_active,
            logo=logo
        )
        return JsonResponse({'status': 'success', 'message': 'Backer created successfully', 'backer_id': backer.id})

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@require_admin_auth
def admin_backer_detail(request, backer_id):
    try:
        backer = Backer.objects.get(id=backer_id)
    except Backer.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Backer not found'}, status=404)
        
    if request.method == 'GET':
        data = {
            'id': backer.id,
            'name': backer.name,
            'logo_url': backer.logo.url if backer.logo else None,
            'url': backer.url,
            'is_active': backer.is_active,
            'created_at': backer.created_at.isoformat()
        }
        return JsonResponse({'status': 'success', 'backer': data})
        
    elif request.method == 'POST':
        name = request.POST.get('name')
        url = request.POST.get('url')
        if 'is_active' in request.POST:
            backer.is_active = request.POST.get('is_active') == 'true'
            
        if 'name' in request.POST:
            backer.name = request.POST.get('name')
        if url is not None:
            backer.url = url
            
        if 'logo' in request.FILES:
            backer.logo = request.FILES.get('logo')
            
        backer.save()
        return JsonResponse({'status': 'success', 'message': 'Backer updated successfully'})
        
    elif request.method == 'DELETE':
        backer.delete()
        return JsonResponse({'status': 'success', 'message': 'Backer deleted successfully'})

    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)


@ensure_csrf_cookie
def admin_failed_waybills_page(request):
    """Render the Failed Waybills tracking page"""
    return render(request, 'admin/failed_waybills.html', {
        'current_path': request.path
    })


@api_view(['GET'])
@require_admin_auth
def admin_api_failed_waybills(request):
    """API endpoint to get unresolved failed waybills"""
    failures = FailedWaybills.objects.select_related('invoice').order_by('-timestamp')
    
    # Optional filtering by status
    status = request.GET.get('status', 'unresolved')
    if status == 'unresolved':
        failures = failures.filter(is_resolved=False)
    elif status == 'resolved':
        failures = failures.filter(is_resolved=True)
        
    data = []
    for f in failures:
        delivery_item = f.invoice.invoice_items.filter(item_id='DELIVERY_001').first()
        delivery_fee = float(delivery_item.item_amount) if delivery_item else 0.0
        
        user = f.invoice.user_id
        user_currency = user.details.first().currency if user.details.exists() else 'NGN'
        
        data.append({
            'id': f.id,
            'invoice_id': f.invoice.invoice_id,
            'customer_name': f.invoice.customer_name or 'N/A',
            'delivery_fee': f"{user_currency} {delivery_fee:,.2f}",
            'delivery_fee_raw': delivery_fee,
            'currency': user_currency,
            'error_message': f.error_message,
            'is_resolved': f.is_resolved,
            'timestamp': f.timestamp.isoformat(),
            'resolved_at': f.resolved_at.isoformat() if f.resolved_at else None
        })
        
    return JsonResponse({'status': 'success', 'data': data})


@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_api_retry_waybill(request, failure_id):
    """API endpoint to manually retry a failed waybill generation"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)
        
    failure = get_object_or_404(FailedWaybills, id=failure_id)
    if failure.is_resolved:
        return JsonResponse({'status': 'error', 'message': 'This waybill has already been successfully generated.'}, status=400)
        
    from api.functions.logistics import process_store_waybill
    success, message = process_store_waybill(failure.invoice)
    
    if success:
        return JsonResponse({'status': 'success', 'message': 'Waybill generated successfully!'})
    else:
        return JsonResponse({'status': 'error', 'message': f'Waybill generation failed again: {message}'}, status=400)


@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_api_batch_retry_waybills(request):
    """API endpoint to manually retry multiple failed waybill generations"""
    try:
        failure_ids = request.data.get('failure_ids', [])
        
        if not failure_ids:
            return JsonResponse({'status': 'error', 'message': 'No waybills selected.'}, status=400)
            
        failures = FailedWaybills.objects.filter(id__in=failure_ids, is_resolved=False)
        from api.functions.logistics import process_store_waybill
        
        success_count = 0
        failed_count = 0
        
        for failure in failures:
            success, message = process_store_waybill(failure.invoice)
            if success:
                success_count += 1
            else:
                failed_count += 1
                
        return JsonResponse({
            'status': 'success', 
            'message': f'Batch process complete. {success_count} succeeded, {failed_count} failed.'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# Sidebar Counters
@api_view(['GET'])
@require_admin_auth
def admin_sidebar_counters(request):
    """API endpoint to get sidebar counters"""
    failed_waybills = FailedWaybills.objects.filter(is_resolved=False).count()
    pending_withdrawals = UserTransactions.objects.filter(
        trx_type='withdrawal', 
        trx_status='pending',
        description__icontains='Insufficient Balance'
    ).count()
    gemini_errors = SystemErrorLog.objects.filter(log_type='gemini').count()
    return JsonResponse({'status': 'success', 'data': {'failed_waybills': failed_waybills, 'pending_withdrawals': pending_withdrawals, 'gemini_errors': gemini_errors}})


# Pending Withdrawals
@ensure_csrf_cookie
def admin_pending_withdrawals_page(request):
    """Render the Pending Withdrawals tracking page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    return render(request, 'admin/failed_withdrawals.html', {
        'current_path': request.path
    })


@api_view(['GET'])
@require_admin_auth
def admin_api_pending_withdrawals(request):
    """API endpoint to get pending withdrawals"""
    from api.user_data.domain_views import get_exchange_rate
    withdrawals = UserTransactions.objects.filter(
        trx_type='withdrawal', 
        trx_status='pending',
        description__icontains='Insufficient Balance'
    ).select_related('user').prefetch_related('user__details').order_by('-timestamp')
    
    total_naira = 0.0
    data = []
    for w in withdrawals:
        user = w.user
        amount = float(w.trx_amount)
        if w.trx_currency == 'NGN':
            total_naira += amount
        else:
            rate = get_exchange_rate(base_currency=w.trx_currency, target_currency='NGN')
            if rate:
                total_naira += amount * float(rate)
            else:
                total_naira += amount
                
        user_name = user.user_id
        details = user.details.first()
        if details and details.first_name:
            user_name = f"{details.first_name} {details.last_name}"
            
        data.append({
            'trx_id': w.trx_id,
            'user_name': user_name,
            'email': user.user_email,
            'amount': f"{w.trx_currency} {amount:,.2f}",
            'amount_raw': amount,
            'currency': w.trx_currency,
            'error_message': w.description,
            'timestamp': w.timestamp.isoformat(),
        })
        
    return JsonResponse({'status': 'success', 'data': data, 'total_naira': total_naira})


@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_api_retry_withdrawal(request, trx_id):
    """API endpoint to manually retry a pending withdrawal"""
    try:
        withdrawal = get_object_or_404(UserTransactions, trx_id=trx_id, trx_type='withdrawal', trx_status='pending')
        
        if withdrawal.user and withdrawal.user.withdrawals_disabled:
            return JsonResponse({'status': 'error', 'message': f'Cannot retry withdrawal: Withdrawals are currently disabled for user {withdrawal.user.user_email}.'}, status=400)

        recipient_code = withdrawal.user_collection_id
        if not recipient_code:
            return JsonResponse({'status': 'error', 'message': 'Missing recipient code for this transaction. Cannot retry.'}, status=400)
            
        from api.external.paystack_api import PaystackAPI
        import uuid
        paystack = PaystackAPI()
        
        # New reference for retry
        reference = f"WDR-{uuid.uuid4().hex[:12].upper()}"
        
        transfer_resp = paystack.initiate_transfer(
            amount=int(float(withdrawal.trx_amount) * 100),
            recipient_code=recipient_code,
            reference=reference,
            reason="Withdrawal"
        )
        
        if transfer_resp.get("status") is True:
            withdrawal.description = reference
            withdrawal.trx_status = 'completed'
            withdrawal.save(update_fields=['description', 'trx_status'])
            return JsonResponse({'status': 'success', 'message': 'Withdrawal retried successfully!'})
        else:
            code = transfer_resp.get("code", "")
            message = transfer_resp.get("message", "").lower()
            if code == "insufficient_balance" or "balance is not enough" in message:
                withdrawal.description = "Pending: Paystack Insufficient Balance"
                withdrawal.save(update_fields=['description'])
                return JsonResponse({'status': 'error', 'message': 'Paystack balance still insufficient.'}, status=400)
            else:
                return JsonResponse({'status': 'error', 'message': f"Transfer failed: {transfer_resp.get('message')}"}, status=400)
                
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_api_batch_retry_withdrawals(request):
    """API endpoint to manually retry multiple pending withdrawals"""
    try:
        trx_ids = request.data.get('trx_ids', [])
        if not trx_ids:
            return JsonResponse({'status': 'error', 'message': 'No transactions selected.'}, status=400)
            
        withdrawals = UserTransactions.objects.filter(trx_id__in=trx_ids, trx_type='withdrawal', trx_status='pending')
        
        from api.external.paystack_api import PaystackAPI
        import uuid
        paystack = PaystackAPI()
        
        success_count = 0
        failed_count = 0
        
        for w in withdrawals:
            if w.user and w.user.withdrawals_disabled:
                failed_count += 1
                continue

            recipient_code = w.user_collection_id
            if not recipient_code:
                failed_count += 1
                continue
                
            reference = f"WDR-{uuid.uuid4().hex[:12].upper()}"
            transfer_resp = paystack.initiate_transfer(
                amount=int(float(w.trx_amount) * 100),
                recipient_code=recipient_code,
                reference=reference,
                reason="Withdrawal"
            )
            
            if transfer_resp.get("status") is True:
                w.description = reference
                w.trx_status = 'completed'
                w.save(update_fields=['description', 'trx_status'])
                success_count += 1
            else:
                code = transfer_resp.get("code", "")
                message = transfer_resp.get("message", "").lower()
                if code == "insufficient_balance" or "balance is not enough" in message:
                    w.description = "Pending: Paystack Insufficient Balance"
                    w.save(update_fields=['description'])
                failed_count += 1
                
        return JsonResponse({
            'status': 'success', 
            'message': f'Batch process complete. {success_count} succeeded, {failed_count} failed.'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_admin_auth
def admin_pos_orders_page(request):
    return render(request, 'admin/pos_orders.html')

@api_view(['GET'])
@require_admin_auth
def admin_api_pos_orders(request):
    try:
        from api.models import POSKitOrder
        status_filter = request.GET.get('status', 'pending')
        
        orders = POSKitOrder.objects.filter(status=status_filter).order_by('-timestamp')
        
        data = []
        for o in orders:
            data.append({
                'id': o.id,
                'email': o.email,
                'phone': o.phone,
                'address': o.address,
                'country': o.country,
                'state': o.state,
                'units': o.units,
                'status': o.status,
                'timestamp': o.timestamp.isoformat(),
                'user_id': o.user.user_id,
            })
            
        return JsonResponse({'status': 'success', 'data': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@api_view(['POST'])
@csrf_exempt
@require_admin_auth
def admin_api_update_pos_order_status(request, order_id):
    try:
        from api.models import POSKitOrder
        from api.tasks import send_pos_order_status_email
        
        order = POSKitOrder.objects.get(id=order_id)
        new_status = request.data.get('status')
        
        if new_status not in ['pending', 'processed']:
            return JsonResponse({'status': 'error', 'message': 'Invalid status.'}, status=400)
            
        if order.status != new_status:
            order.status = new_status
            order.save()
            
            if new_status == 'processed':
                # No target_currency and final_amount available directly here easily,
                # but we can pass None or fetch from transaction if needed.
                # However, the processed email just needs to say it is processed.
                dashboard_url = f"{request.scheme}://{request.get_host()}/pos"
                send_pos_order_status_email.delay(order.id, 'USD', 0, dashboard_url)
                
        return JsonResponse({'status': 'success', 'message': f'Order status updated to {new_status}.'})
    except POSKitOrder.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Order not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@require_admin_auth
def admin_error_logs_page(request):

    # Fetch logs
    gemini_errors = SystemErrorLog.objects.filter(log_type='gemini').order_by('-timestamp')
    
    failed_waybills_count = FailedWaybills.objects.filter(is_resolved=False).count()
    failed_withdrawals_count = UserTransactions.objects.filter(
        trx_type='withdrawal', 
        trx_status='pending',
        description__icontains='Insufficient Balance'
    ).count()
    gemini_errors_count = gemini_errors.count()
    
    context = {
        'gemini_errors': gemini_errors,
        'failed_waybills_count': failed_waybills_count,
        'failed_withdrawals_count': failed_withdrawals_count,
        'gemini_errors_count': gemini_errors_count,
        'active_menu': 'error_logs',
    }
    
    return render(request, 'admin/error_logs.html', context)

@require_admin_auth
def admin_delete_gemini_error(request, error_id):
    if request.method == 'POST':
        try:
            error_log = SystemErrorLog.objects.get(id=error_id, log_type='gemini')
            error_log.delete()
            return JsonResponse({'status': 'success', 'message': 'Log deleted successfully.'})
        except SystemErrorLog.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Error log not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


@ensure_csrf_cookie
def admin_expired_accounts_page(request):
    """Render admin expired accounts page"""
    if not check_admin_auth(request):
        return redirect('admin_login_page')
    from api.models import SubscriptionPlans
    plans = SubscriptionPlans.objects.all().order_by('uniq_id')
    
    return render(request, 'admin/expired_accounts.html', {
        'active_menu': 'expired_accounts',
        'plans': plans
    })

@require_admin_auth
def admin_api_expired_accounts(request):
    """API endpoint to get expired accounts"""
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        search = request.GET.get('search', '').strip().lower()
        now = timezone.now()
        
        # Fetch all businesses since subscription_expiry is encrypted
        # and we need to decrypt it to check the expiry.
        all_businesses = BusinessDetails.objects.all().select_related('user')
        expired_businesses = []
        
        for biz in all_businesses:
            expiry_str = biz.subscription_expiry
            if not expiry_str:
                expired_businesses.append(biz)
            else:
                try:
                    expiry_date = datetime.fromisoformat(expiry_str)
                    if expiry_date < now:
                        expired_businesses.append(biz)
                except ValueError:
                    # If date parsing fails, consider it expired
                    expired_businesses.append(biz)
        
        from api.models import SubscriptionPlans
        all_plans = {p.uniq_id: p.plan_name for p in SubscriptionPlans.objects.all()}
        
        users_data = []
        for biz in expired_businesses:
            user = biz.user
            if not user:
                continue
                
            plan_name = all_plans.get(biz.plan_code, "Starter (Free)")
            email = user.user_email or ''
            user_id_str = str(user.user_id) if user.user_id else ''
            
            # Apply search filter if provided
            if search:
                match = (
                    search in email.lower() or
                    search in user_id_str.lower() or
                    search in plan_name.lower() or
                    (biz.store_name and search in biz.store_name.lower())
                )
                if not match:
                    continue
            
            users_data.append({
                'user_id': user.user_id,
                'email': email,
                'current_plan': plan_name,
                'store_name': biz.store_name or '',
                'expiry_date': biz.subscription_expiry if biz.subscription_expiry else now.isoformat()
            })
            
        paginator = Paginator(users_data, per_page)
        page_obj = paginator.get_page(page)
        
        return JsonResponse({
            'status': 'success',
            'users': list(page_obj),
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'per_page': per_page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@require_admin_auth
def admin_api_assign_plan(request):
    """API endpoint to manually assign a plan to a user"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_id = data.get('user_id')
            plan_id = data.get('plan_id')
            months = int(data.get('months', 1))
            
            if not all([user_id, plan_id, months]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields'})
                
            from api.models import UserSecure, SubscriptionPlans, SubscriptionInvoices
            from dateutil.relativedelta import relativedelta
            from api.tasks import send_manual_plan_assignment_email
            
            user = UserSecure.objects.get(user_id=user_id)
            plan = SubscriptionPlans.objects.get(uniq_id=plan_id)
            biz = BusinessDetails.objects.filter(user=user).first()
            
            if not biz:
                return JsonResponse({'status': 'error', 'message': 'Business details not found for user'})
            
            # Update expiry and plan
            now = timezone.now()
            
            # If they were expired, start from now
            start_date = now
            if biz.subscription_expiry:
                try:
                    existing_expiry = datetime.fromisoformat(biz.subscription_expiry)
                    if existing_expiry >= now:
                        start_date = existing_expiry
                except ValueError:
                    pass
                    
            new_expiry = start_date + relativedelta(months=months)
            
            biz.plan_code = plan.uniq_id
            biz.subscription_expiry = new_expiry
            biz.save(update_fields=['plan_code', '_subscription_expiry'])
            
            # Create a zero-value invoice for auditing
            amount = 0
            if months == 1:
                amount = plan.one_amount
            elif months == 3:
                amount = plan.three_months
            elif months == 6:
                amount = plan.six_months
            elif months == 12:
                amount = plan.twelve_months
                
            SubscriptionInvoices.objects.create(
                user=user,
                plan_id=plan.uniq_id,
                amount=amount,
                invoice_id=f"MANUAL_ASSIGN_{int(now.timestamp())}",
                invoice_status="completed",
                invoice_payment_type="wallet",
                invoice_note=f"Manually assigned by admin for {months} months"
            )
            
            # Send congratulatory email asynchronously
            send_manual_plan_assignment_email.apply_async(args=[user.user_id, plan.plan_name, months, new_expiry.strftime('%Y-%m-%d')])
            
            return JsonResponse({'status': 'success', 'message': f'Plan {plan.plan_name} assigned successfully for {months} months.'})
            
        except UserSecure.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'})
        except SubscriptionPlans.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Plan not found'})
        except Exception as e:
            logger.error(f"Error in manual plan assignment: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@require_admin_auth
def admin_invoices_page(request):
    """Render admin invoices management page"""
    return render(request, 'admin/invoices.html')


@api_view(['GET'])
@require_admin_auth
def admin_api_invoices(request):
    """Get paginated list of all platform invoices with stats and filters"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 100)
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '').strip().lower()
        channel_filter = request.GET.get('channel', '').strip().lower()
        type_filter = request.GET.get('type', '').strip().lower()
        user_id_filter = request.GET.get('user_id', '').strip()

        invoices_query = UserInvoices.objects.select_related('user_id').prefetch_related('invoice_items').order_by('-timestamp')
        
        if user_id_filter:
            invoices_query = invoices_query.filter(user_id__user_id=user_id_filter)

        if search:
            invoices_query = invoices_query.filter(
                Q(invoice_id__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(customer_email__icontains=search) |
                Q(customer_phone__icontains=search) |
                Q(user_id__user_email__icontains=search) |
                Q(user_id__user_id__icontains=search)
            )

        if status_filter in ['pending', 'completed']:
            invoices_query = invoices_query.filter(invoice_status=status_filter)

        if channel_filter == 'online':
            invoices_query = invoices_query.filter(is_online_order=True)
        elif channel_filter == 'direct':
            invoices_query = invoices_query.filter(is_online_order=False)

        if type_filter in ['instant', 'installment']:
            invoices_query = invoices_query.filter(invoice_type=type_filter)

        # Overview Stats (across all invoices)
        total_invoices_count = UserInvoices.objects.count()
        completed_invoices_count = UserInvoices.objects.filter(invoice_status='completed').count()
        pending_invoices_count = UserInvoices.objects.filter(invoice_status='pending').count()
        online_orders_count = UserInvoices.objects.filter(is_online_order=True).count()

        paginator = Paginator(invoices_query, per_page)
        page_obj = paginator.get_page(page)

        user_ids = [inv.user_id_id for inv in page_obj if inv.user_id_id]
        user_details_map = {
            ud.user_id: ud for ud in UserDetails.objects.filter(user__in=user_ids)
        }
        biz_details_map = {
            bd.user_id: bd for bd in BusinessDetails.objects.filter(user__in=user_ids)
        }

        data = []
        for inv in page_obj:
            user_sec = inv.user_id
            user_pk = user_sec.id if user_sec else None
            ud = user_details_map.get(user_pk)
            bd = biz_details_map.get(user_pk)

            items = list(inv.invoice_items.all())
            items_total = sum(float(it.item_amount) * it.item_quantity for it in items)
            items_count = sum(it.item_quantity for it in items)

            currency = (ud.currency if ud and ud.currency else 'NGN').upper()
            biz_name = bd.business_name if bd and bd.business_name else (bd.store_name if bd and bd.store_name else 'N/A')

            data.append({
                'id': inv.id,
                'invoice_id': inv.invoice_id,
                'invoice_status': inv.invoice_status,
                'invoice_type': inv.invoice_type,
                'invoice_payment_type': inv.invoice_payment_type or 'instant',
                'customer_name': inv.customer_name or 'Walk-in Customer',
                'customer_email': inv.customer_email or '',
                'customer_phone': inv.customer_phone or '',
                'is_online_order': inv.is_online_order,
                'delivery_status': inv.delivery_status or 'pending',
                'delivery_type': inv.delivery_type or 'self',
                'tracking_number': inv.tracking_number or '',
                'items_count': items_count,
                'total_amount': items_total,
                'currency': currency,
                'merchant': {
                    'user_id': user_sec.user_id if user_sec else '',
                    'email': user_sec.user_email if user_sec else '',
                    'business_name': biz_name,
                },
                'timestamp': inv.timestamp.strftime('%Y-%m-%d %H:%M') if inv.timestamp else '',
                'due_date': inv.due_date.strftime('%Y-%m-%d') if inv.due_date else '',
            })

        return Response({
            'status': True,
            'stats': {
                'total_invoices': total_invoices_count,
                'completed_invoices': completed_invoices_count,
                'pending_invoices': pending_invoices_count,
                'online_orders': online_orders_count,
            },
            'data': data,
            'pagination': {
                'current_page': page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'per_page': per_page,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })
    except Exception as e:
        logger.error(f"Error in admin_api_invoices: {str(e)}\n{traceback.format_exc()}")
        return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@require_admin_auth
def admin_api_invoice_detail(request, invoice_id):
    """Get complete line items and detail for a specific invoice"""
    try:
        invoice = UserInvoices.objects.filter(invoice_id=invoice_id).select_related('user_id').first()
        if not invoice:
            return Response({'status': False, 'message': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)

        user_sec = invoice.user_id
        ud = UserDetails.objects.filter(user=user_sec).first() if user_sec else None
        bd = BusinessDetails.objects.filter(user=user_sec).first() if user_sec else None

        currency = (ud.currency if ud and ud.currency else 'NGN').upper()
        biz_name = bd.business_name if bd and bd.business_name else (bd.store_name if bd and bd.store_name else 'N/A')

        invoice_items = []
        items_total = 0.0
        for item in invoice.invoice_items.all():
            line_total = float(item.item_amount) * item.item_quantity
            items_total += line_total
            invoice_items.append({
                'id': item.id,
                'item_id': item.item_id,
                'item_name': item.item_name,
                'item_amount': float(item.item_amount),
                'item_quantity': item.item_quantity,
                'line_total': line_total,
                'color_name': item.color_name or '',
                'color_hex': item.color_hex or '',
                'size': item.size or '',
            })

        return Response({
            'status': True,
            'data': {
                'id': invoice.id,
                'invoice_id': invoice.invoice_id,
                'invoice_status': invoice.invoice_status,
                'invoice_type': invoice.invoice_type,
                'invoice_payment_type': invoice.invoice_payment_type or 'instant',
                'invoice_note': invoice.invoice_note or '',
                'customer_name': invoice.customer_name or 'Walk-in Customer',
                'customer_email': invoice.customer_email or '',
                'customer_phone': invoice.customer_phone or '',
                'is_online_order': invoice.is_online_order,
                'delivery_status': invoice.delivery_status or 'pending',
                'delivery_type': invoice.delivery_type or 'self',
                'delivery_address': invoice.delivery_address or '',
                'delivery_country': invoice.delivery_country or '',
                'delivery_state': invoice.delivery_state or '',
                'delivery_lga': invoice.delivery_lga or '',
                'delivery_postal_code': invoice.delivery_postal_code or '',
                'tracking_number': invoice.tracking_number or '',
                'designated_account_number': invoice.designated_account_number or '',
                'designated_account_name': invoice.designated_account_name or '',
                'designated_bank_name': invoice.designated_bank_name or '',
                'total_amount': items_total,
                'currency': currency,
                'merchant': {
                    'user_id': user_sec.user_id if user_sec else '',
                    'email': user_sec.user_email if user_sec else '',
                    'business_name': biz_name,
                    'vat_percentage': float(bd.vat_percentage) if bd and bd.vat_percentage is not None else 0.0,
                },
                'items': invoice_items,
                'timestamp': invoice.timestamp.strftime('%Y-%m-%d %H:%M:%S') if invoice.timestamp else '',
                'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else '',
            }
        })
    except Exception as e:
        logger.error(f"Error in admin_api_invoice_detail: {str(e)}\n{traceback.format_exc()}")
        return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Template Views
@require_admin_auth
def admin_tickets_page(request):
    return render(request, 'admin/tickets.html')

@require_admin_auth
def admin_ticket_create_page(request):
    return render(request, 'admin/ticket_create.html')

@require_admin_auth
def admin_ticket_details_page(request, ticket_id):
    return render(request, 'admin/ticket_details.html', {'ticket_id': ticket_id})

# API Views
@api_view(['GET', 'POST'])
@require_admin_auth
def admin_api_tickets(request):
    if request.method == 'GET':
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        priority_filter = request.GET.get('priority', '')
        department_filter = request.GET.get('department', '')
        assigned_admin_filter = request.GET.get('assigned_admin', '')
        
        tickets_query = Ticket.objects.all().select_related('department', 'assigned_admin').prefetch_related('affected_users').order_by('-last_activity_at')
        
        if search:
            tickets_query = tickets_query.filter(
                Q(ticket_number__icontains=search) |
                Q(subject__icontains=search) |
                Q(affected_users__user_email__icontains=search) |
                Q(affected_users__details__first_name__icontains=search)
            ).distinct()
            
        if status_filter and status_filter != 'all':
            tickets_query = tickets_query.filter(status=status_filter)
        if priority_filter and priority_filter != 'all':
            tickets_query = tickets_query.filter(priority=priority_filter)
        if department_filter:
            tickets_query = tickets_query.filter(department_id=department_filter)
        if assigned_admin_filter:
            tickets_query = tickets_query.filter(assigned_admin__user_id=assigned_admin_filter)
            
        paginator = Paginator(tickets_query, per_page)
        page_obj = paginator.get_page(page)
        
        tickets_data = []
        for t in page_obj:
            tickets_data.append({
                'id': t.id,
                'ticket_number': t.ticket_number,
                'subject': t.subject,
                'status': t.status,
                'priority': t.priority,
                'department': {'id': t.department.id, 'name': t.department.name} if t.department else None,
                'assigned_admin': {'user_id': t.assigned_admin.user_id, 'email': t.assigned_admin.user_email} if t.assigned_admin else None,
                'affected_users_count': t.affected_users.count(),
                'created_at': t.created_at.isoformat(),
                'last_activity_at': t.last_activity_at.isoformat(),
            })
            
        return Response({
            'status': True,
            'tickets': tickets_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_prev': page_obj.has_previous()
            }
        })
    
    elif request.method == 'POST':
        try:
            subject = request.data.get('subject')
            department_id = request.data.get('department_id')
            assigned_admin_id = request.data.get('assigned_admin_id')
            priority = request.data.get('priority', 'mid')
            status_val = request.data.get('status', 'pending')
            affected_users_ids = request.data.get('affected_users', [])
            initial_message = request.data.get('message')
            
            if not subject or not initial_message or not department_id:
                return Response({'status': False, 'message': 'Subject, initial message, and department are required'}, status=status.HTTP_400_BAD_REQUEST)
                
            department = Department.objects.get(id=department_id)
            
            admin_user = None
            if assigned_admin_id:
                admin_user = UserSecure.objects.get(user_id=assigned_admin_id)
                
            current_admin = UserSecure.objects.get(user_id=request.session.get('admin_user_id'))
            
            with transaction.atomic():
                ticket = Ticket.objects.create(
                    subject=subject,
                    department=department,
                    assigned_admin=admin_user,
                    priority=priority,
                    status=status_val,
                    created_by=current_admin
                )
                
                if affected_users_ids:
                    users = UserSecure.objects.filter(user_id__in=affected_users_ids)
                    ticket.affected_users.set(users)
                
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender_admin=current_admin,
                    message=initial_message,
                    message_type='public_reply'
                )
            
            from .tasks import send_ticket_email_task
            send_ticket_email_task.delay(ticket.id, 'created')
            
            return Response({'status': True, 'message': 'Ticket created successfully', 'ticket_number': ticket.ticket_number})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@require_admin_auth
def admin_api_ticket_detail(request, ticket_id):
    try:
        ticket = Ticket.objects.prefetch_related('affected_users', 'department', 'assigned_admin').get(ticket_number=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'status': False, 'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        affected_users = []
        for u in ticket.affected_users.all():
            first_name = ""
            details = u.details.first()
            if details:
                first_name = f"{details.first_name} {details.last_name}".strip()
            affected_users.append({'user_id': u.user_id, 'email': u.user_email, 'name': first_name})
            
        data = {
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'subject': ticket.subject,
            'status': ticket.status,
            'priority': ticket.priority,
            'department': {'id': ticket.department.id, 'name': ticket.department.name} if ticket.department else None,
            'assigned_admin': {'user_id': ticket.assigned_admin.user_id, 'email': ticket.assigned_admin.user_email} if ticket.assigned_admin else None,
            'affected_users': affected_users,
            'created_at': ticket.created_at.isoformat(),
            'last_activity_at': ticket.last_activity_at.isoformat(),
        }
        return Response({'status': True, 'ticket': data})
        
    elif request.method == 'PATCH':
        try:
            current_admin = UserSecure.objects.get(user_id=request.session.get('admin_user_id'))
            
            changes = []
            send_status_email = False
            
            if 'status' in request.data:
                old_status = ticket.status
                ticket.status = request.data['status']
                if old_status != ticket.status:
                    changes.append(f"Status changed from {old_status} to {ticket.status}")
                    send_status_email = True
                
            if 'priority' in request.data:
                old_priority = ticket.priority
                ticket.priority = request.data['priority']
                if old_priority != ticket.priority:
                    changes.append(f"Priority changed from {old_priority} to {ticket.priority}")
                
            if 'department_id' in request.data:
                dep_id = request.data['department_id']
                if dep_id:
                    department = Department.objects.get(id=dep_id)
                    old_dep = ticket.department.name if ticket.department else 'None'
                    ticket.department = department
                    if old_dep != department.name:
                        changes.append(f"Department changed from {old_dep} to {department.name}")
                
            if 'assigned_admin_id' in request.data:
                admin_id = request.data['assigned_admin_id']
                if admin_id:
                    admin_user = UserSecure.objects.get(user_id=admin_id)
                    old_admin = ticket.assigned_admin.user_email if ticket.assigned_admin else 'None'
                    ticket.assigned_admin = admin_user
                    if old_admin != admin_user.user_email:
                        changes.append(f"Assigned to {admin_user.user_email}")
                else:
                    ticket.assigned_admin = None
                    changes.append("Assignment removed")
                    
            if 'affected_users' in request.data:
                users = UserSecure.objects.filter(user_id__in=request.data['affected_users'])
                ticket.affected_users.set(users)
                changes.append("Affected users updated")
                
            with transaction.atomic():
                ticket.save()
                for change in changes:
                    TicketMessage.objects.create(
                        ticket=ticket,
                        sender_admin=current_admin,
                        message=change,
                        message_type='system'
                    )
            
            if send_status_email:
                from .tasks import send_ticket_email_task
                send_ticket_email_task.delay(ticket.id, 'status_change')

            return Response({'status': True, 'message': 'Ticket updated successfully'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
@require_admin_auth
def admin_api_ticket_messages(request, ticket_id):
    try:
        ticket = Ticket.objects.get(ticket_number=ticket_id)
    except Ticket.DoesNotExist:
        return Response({'status': False, 'message': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        messages = ticket.messages.all().select_related('sender_admin', 'sender_user')
        msg_data = []
        for m in messages:
            sender_name = 'System'
            sender_type = 'system'
            if m.sender_admin:
                sender_name = m.sender_admin.user_email
                sender_type = 'admin'
            elif m.sender_user:
                sender_name = m.sender_user.user_email
                sender_type = 'customer'
                
            msg_data.append({
                'id': m.id,
                'sender': sender_name,
                'sender_type': sender_type,
                'message': m.message,
                'message_type': m.message_type,
                'created_at': m.created_at.isoformat()
            })
            
        return Response({'status': True, 'messages': msg_data})
        
    elif request.method == 'POST':
        message_text = request.data.get('message')
        message_type = request.data.get('message_type', 'public_reply')
        
        if not message_text:
            return Response({'status': False, 'message': 'Message cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            current_admin = UserSecure.objects.get(user_id=request.session.get('admin_user_id'))
            
            with transaction.atomic():
                msg = TicketMessage.objects.create(
                    ticket=ticket,
                    sender_admin=current_admin,
                    message=message_text,
                    message_type=message_type
                )
                ticket.last_activity_at = timezone.now()
                ticket.save(update_fields=['last_activity_at'])
                
            if message_type == 'public_reply':
                from .tasks import send_ticket_email_task
                send_ticket_email_task.delay(ticket.id, 'reply')
                
            return Response({'status': True, 'message': 'Reply sent successfully'})
        except Exception as e:
            return Response({'status': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@require_admin_auth
def admin_departments_page(request):
    """Render departments management page"""
    return render(request, 'admin/departments.html')

@api_view(['GET', 'POST'])
@require_admin_auth
def admin_api_departments(request):
    if request.method == 'POST':
        name = request.data.get('name')
        description = request.data.get('description', '')
        active = request.data.get('active', True)
        
        if not name:
            return Response({'status': False, 'message': 'Department name is required'})
            
        if Department.objects.filter(name__iexact=name).exists():
            return Response({'status': False, 'message': 'Department with this name already exists'})
            
        dept = Department.objects.create(
            name=name,
            description=description,
            active=bool(active)
        )
        return Response({'status': True, 'message': 'Department created successfully'})
        
    # GET list of departments with members count
    departments = Department.objects.prefetch_related('members').all().order_by('-created_at')
    
    data = []
    for d in departments:
        members_data = []
        for m in d.members.all():
            members_data.append({
                'user_id': m.user_id,
                'email': m.user_email
            })
            
        data.append({
            'id': d.id,
            'name': d.name,
            'description': d.description,
            'active': d.active,
            'members': members_data,
            'members_count': len(members_data),
            'created_at': d.created_at.isoformat() if d.created_at else None
        })
        
    return Response({'status': True, 'departments': data})

@api_view(['PUT', 'DELETE'])
@require_admin_auth
def admin_api_department_detail(request, department_id):
    try:
        dept = Department.objects.get(id=department_id)
    except Department.DoesNotExist:
        return Response({'status': False, 'message': 'Department not found'})
        
    if request.method == 'DELETE':
        dept.delete()
        return Response({'status': True, 'message': 'Department deleted'})
        
    if request.method == 'PUT':
        name = request.data.get('name', dept.name)
        description = request.data.get('description', dept.description)
        active = request.data.get('active', dept.active)
        members = request.data.get('members', None)
        
        if name != dept.name and Department.objects.filter(name__iexact=name).exists():
            return Response({'status': False, 'message': 'Department with this name already exists'})
            
        dept.name = name
        dept.description = description
        dept.active = bool(active)
        dept.save()
        
        if members is not None:
            admins = UserSecure.objects.filter(user_id__in=members, is_superuser=True)
            dept.members.set(admins)
            
        return Response({'status': True, 'message': 'Department updated'})

@api_view(['GET'])
@require_admin_auth
def admin_api_admins_search(request):
    """Search for admin users by name or email or user_id to assign to departments"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return Response({'status': True, 'admins': []})
        
    matching_user_uniq_ids = set()
    
    try:
        from api.models import UserDetails
        matching_details = UserDetails.objects.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).select_related('user').filter(
            user__is_superuser=True,
            user__is_active=True
        )
        for details in matching_details:
            if details.user:
                matching_user_uniq_ids.add(details.user.uniq_id)
    except Exception:
        pass
        
    try:
        users_by_email = set(UserSecure.objects.filter(
            is_superuser=True,
            is_active=True,
            user_email__icontains=query
        ).values_list('uniq_id', flat=True))
        matching_user_uniq_ids.update(users_by_email)
    except Exception:
        pass
        
    try:
        users_by_id = set(UserSecure.objects.filter(
            is_superuser=True,
            is_active=True,
            user_id__icontains=query
        ).values_list('uniq_id', flat=True))
        matching_user_uniq_ids.update(users_by_id)
    except Exception:
        pass
        
    user_uniq_ids_list = list(matching_user_uniq_ids)[:20]
    
    admins_query = UserSecure.objects.filter(
        uniq_id__in=user_uniq_ids_list
    ).prefetch_related('details')
    
    admins_data = []
    for user in admins_query:
        first_name = ''
        last_name = ''
        full_name = user.user_id
        details = user.details.first()
        if details:
            first_name = details.first_name or ''
            last_name = details.last_name or ''
            name_parts = [first_name, last_name]
            full_name = ' '.join([n for n in name_parts if n]).strip()
            if not full_name:
                full_name = user.user_id
                
        admins_data.append({
            'user_id': user.user_id,
            'email': user.user_email or '',
            'full_name': full_name
        })
        
    return Response({'status': True, 'admins': admins_data})
