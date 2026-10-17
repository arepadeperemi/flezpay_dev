from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from api.models import LiveChat, LiveChatMessage, StoreVisitor, BusinessDetails, UserDetails, UserPayroll, UserTransactions
from api.tasks import (
    monitor_wallet_balances,
    send_pending_livechat_notifications,
    send_pending_visitor_livechat_notifications,
    send_business_reports,
    process_automatic_payroll,
    notify_subscription_expiry,
    send_low_stock_alerts
)

class Command(BaseCommand):
    help = 'Test execute all celery tasks synchronously'

    def handle(self, *args, **options):
        self.stdout.write('--- Starting Tasks Execution Test ---')
        
        # 1. Setup dynamic DB state for the livechat visitor notification test
        self.stdout.write('Setting up test chat database state for visitor notification...')
        try:
            # Get any business
            business = BusinessDetails.objects.first()
            if not business:
                self.stdout.write(self.style.ERROR('No business found in database. Cannot test livechat notifications.'))
            else:
                # Find or create a test visitor with an email
                visitor, _ = StoreVisitor.objects.get_or_create(
                    session_id='test_visitor_session_123',
                    store=business,
                    defaults={
                        'visitor_name': 'Test Visitor',
                        'visitor_email': 'test_visitor@flezpay.com',
                        'is_online': False
                    }
                )
                visitor.visitor_email = 'test_visitor@flezpay.com' # Ensure email is set
                visitor.is_online = False
                visitor.save()
                
                # Find or create an open chat
                chat, _ = LiveChat.objects.get_or_create(
                    visitor=visitor,
                    store=business,
                    status='open'
                )
                chat.notification_sent = False
                chat.save()
                
                # Create a new unread message from agent
                LiveChatMessage.objects.create(
                    chat=chat,
                    sender_type='agent',
                    message_text='Hello! This is a test response from the support team.',
                    is_read=False
                )
                self.stdout.write(self.style.SUCCESS('✓ Successfully created unread agent message for test visitor.'))
                
                # --- Payroll Test Setup ---
                # Ensure business has auto payroll enabled
                business.enable_auto_payroll = True
                business.payroll_overdraft = 50000.00
                business.save()
                
                # Ensure user details country is NG
                user_details, _ = UserDetails.objects.get_or_create(user=business.user)
                user_details.user_country = 'NG'
                user_details.save()
                
                # Create a daily active test payroll
                payroll, _ = UserPayroll.objects.get_or_create(
                    staff_user=business.user,
                    defaults={
                        'user_id': business.user,
                        'account_name': 'Test Employee Payout',
                        'account_number': '2085175181',
                        'bank_name': 'Access Bank',
                        'account_id': '033',
                        'pay_status': 'active',
                    }
                )
                # Ensure values match daily active status using model setters
                payroll.pay_status = 'active'
                payroll.set_pay_frequency('daily')
                payroll.set_pay_date('2026-07-30')
                payroll.set_pay_amount(50000.00)
                payroll.set_allowances(2000.00)
                payroll.set_deductions(1000.00)
                payroll.paystack_recipient_code = 'RCP_test123'
                payroll.save()
                self.stdout.write(self.style.SUCCESS('✓ Successfully configured database state for automated payroll test.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to set up test state: {e}'))

        # 2. Run the tasks list
        tasks_to_test = [
            ('monitor_wallet_balances', monitor_wallet_balances),
            ('send_pending_livechat_notifications', send_pending_livechat_notifications),
            ('send_pending_visitor_livechat_notifications', send_pending_visitor_livechat_notifications),
            ('send_business_reports', send_business_reports),
            ('process_automatic_payroll', process_automatic_payroll),
            ('notify_subscription_expiry', notify_subscription_expiry),
            ('send_low_stock_alerts', send_low_stock_alerts),
        ]
        
        for name, task_func in tasks_to_test:
            self.stdout.write(f'Running task: {name}...')
            try:
                if name in ['send_pending_livechat_notifications', 'send_pending_visitor_livechat_notifications']:
                    # Mock timezone.now to be 10 minutes in the future to bypass the 1-minute delay check
                    future_now = timezone.now() + timedelta(minutes=10)
                    with patch('django.utils.timezone.now', return_value=future_now):
                        task_func()
                elif name == 'process_automatic_payroll':
                    # Mock calculation of available balance and Paystack bulk transfer API calls
                    with patch('api.tasks.calculate_total_balance', return_value=1000000.00):
                        with patch('api.external.paystack_api.PaystackAPI.bulk_transfer', return_value={"status": True, "data": []}):
                            task_func()
                else:
                    task_func()
                self.stdout.write(self.style.SUCCESS(f'✓ Task {name} executed successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Task {name} failed: {e}'))
                
        # 3. Verify if livechat notification was triggered
        try:
            chat = LiveChat.objects.filter(visitor__session_id='test_visitor_session_123').first()
            if chat and chat.notification_sent:
                self.stdout.write(self.style.SUCCESS('✓ Verification Success: Visitor chat notification was triggered! (notification_sent=True)'))
            else:
                self.stdout.write(self.style.ERROR('✗ Verification Failure: Visitor chat notification was NOT triggered.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to verify livechat notification state: {e}'))
            
        # 4. Verify if payroll transaction was created
        try:
            # We check if there is a pending payroll transaction created today for our account number
            tx = UserTransactions.objects.filter(
                trx_source='Payroll',
                user_collection_id='2085175181',
                trx_status='pending'
            ).first()
            if tx:
                self.stdout.write(self.style.SUCCESS(f'✓ Verification Success: Payroll transaction created successfully! (Amount: {tx.trx_amount} NGN, Ref/Desc: {tx.description})'))
            else:
                self.stdout.write(self.style.ERROR('✗ Verification Failure: Payroll transaction was NOT created.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to verify payroll transaction state: {e}'))
            
        self.stdout.write('--- Tasks Execution Test Completed ---')
