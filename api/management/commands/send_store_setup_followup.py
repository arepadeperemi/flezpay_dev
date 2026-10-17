from django.core.management.base import BaseCommand
from api.models import BusinessDetails, UserItems
from api.tasks import check_store_setup_followup_task
import time

class Command(BaseCommand):
    help = 'Sends the store setup followup email to existing users who meet the conditions.'

    def handle(self, *args, **options):
        # Find all businesses where store_setup is True and email wasn't sent yet
        businesses = BusinessDetails.objects.filter(store_setup=True, has_received_setup_email=False).select_related('user')
        triggered_count = 0

        for biz in businesses:
            user = biz.user
            if not user:
                continue
                
            # Check if they have any featured items
            featured_count = UserItems.objects.filter(user=user, is_featured=True).count()
            
            if featured_count <= 0:
                # Queue the celery task immediately
                check_store_setup_followup_task.apply_async(args=[user.user_id])
                triggered_count += 1
                
        self.stdout.write(self.style.SUCCESS(f"Successfully queued followup emails for {triggered_count} existing users."))
