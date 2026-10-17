"""
Management command to set up the wallet monitoring periodic task in the database.
Run this once to create the periodic task for django-celery-beat.

Usage: python manage.py setup_wallet_monitor
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule


class Command(BaseCommand):
    help = 'Set up the wallet monitoring periodic task in the database'

    def handle(self, *args, **options):
        self.stdout.write('Setting up wallet monitoring periodic task...')
        
        # Create or get the interval schedule (every 5 seconds)
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.SECONDS,
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created interval schedule: every {schedule.every} {schedule.period}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Using existing interval schedule: every {schedule.every} {schedule.period}')
            )
        
        # Create or update the periodic task
        task, created = PeriodicTask.objects.get_or_create(
            name='monitor-wallet-balances',
            defaults={
                'task': 'api.tasks.monitor_wallet_balances',
                'interval': schedule,
                'enabled': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created periodic task: monitor-wallet-balances')
            )
        else:
            # Update existing task to ensure it's correct
            task.task = 'api.tasks.monitor_wallet_balances'
            task.interval = schedule
            task.enabled = True
            task.save()
            self.stdout.write(
                self.style.SUCCESS('✓ Updated periodic task: monitor-wallet-balances')
            )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Wallet monitoring task is now set up!'))
        self.stdout.write('')
        self.stdout.write('Task Details:')
        self.stdout.write(f'  Name: {task.name}')
        self.stdout.write(f'  Task: {task.task}')
        self.stdout.write(f'  Schedule: Every {schedule.every} {schedule.period}')
        self.stdout.write(f'  Enabled: {task.enabled}')
        self.stdout.write('')
        self.stdout.write('Make sure Celery Beat is running with DatabaseScheduler:')
        self.stdout.write('  celery -A flezpay beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler')

