"""
Django management command to run the Arc USDC WebSocket listener.

Usage:
    python manage.py run_arc_listener

This is a long-running process. Run it as a separate supervised service:
    systemd:  flezpay-arc-listener.service
    Docker:   arc-listener container
    Heroku:   Procfile worker: python manage.py run_arc_listener
"""
import asyncio
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger('arc_payments.listener')


class Command(BaseCommand):
    help = 'Start the Arc USDC WebSocket listener (long-running process)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            '✓ Starting Arc USDC WebSocket listener...\n'
            '  Press Ctrl+C to stop.\n'
        ))

        from arc_payments.config import ARC_ENABLED, ARC_WS_URL, ARC_NETWORK
        if not ARC_ENABLED:
            self.stderr.write(self.style.ERROR(
                'ARC_ENABLED is False. Set ARC_ENABLED=true in .env to enable.'
            ))
            return

        self.stdout.write(f'  Network:  {ARC_NETWORK}')
        self.stdout.write(f'  WS URL:   {ARC_WS_URL[:50]}...\n')

        from arc_payments.listener import listen_forever
        try:
            asyncio.run(listen_forever())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nArc listener stopped by user.'))
